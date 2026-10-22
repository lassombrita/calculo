"""Orquestación pura del cálculo de una región: área, malla 3D, recomendación y volumen.

Responsabilidad:
Ser la única ruta de cálculo que usa la interfaz. Antes existían dos copias de esta lógica
(``CalculationWorker.run`` y ``MainWindow._execute_calculation_sync``) y los tests solo
ejercitaban la segunda. Este módulo no importa Qt: se ejecuta igual en un hilo secundario,
en el hilo principal (modo síncrono de las pruebas) o, en el futuro, en un proceso aparte.

Orden de los pasos (pensado para que la interfaz responda pronto):
1. Área 2D (rápida y prioritaria en los mensajes de error).
2. Verificación numérica del eje (sin SymPy pesado): si atraviesa la región se corta aquí.
3. Malla 3D (NumPy, milisegundos): se entrega por ``on_mesh`` antes del cálculo simbólico.
4. Recomendación y volumen exacto (SymPy, puede tardar segundos).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

import numpy as np

from integrallab.core.operations import NumericResult, integrate_definite, subtract_expressions
from integrallab.core.parser import ParsedExpression
from integrallab.core.solids import (
    AxisOrientation,
    MethodRecommendation,
    Region2D,
    RevolutionAxis,
    SolidMesh3D,
    SolidMethod,
    VolumeResult,
    axis_crossing_error,
    calculate_revolution_volume,
    domain_error,
    generate_solid_mesh,
    recommend_method,
    numeric_volume,
)

# Resolución de la malla que se envía al visor. El giro es exacto, así que 64 × 48 ya da un
# contorno liso; Matplotlib la submuestrea por su cuenta (ver PlotCanvas3D).
MESH_RADIAL: int = 64
MESH_AXIAL: int = 48


class CalculationCancelled(Exception):
    """El cálculo se abandonó porque el usuario lo canceló o lanzó otro más reciente."""


@dataclass(frozen=True)
class CalculationRequest:
    """Datos de entrada de un cálculo (ya parseados y validados por la interfaz)."""

    f: ParsedExpression
    g: ParsedExpression | None
    a_text: str
    b_text: str
    axis: RevolutionAxis
    method: SolidMethod | None
    mesh_radial: int = MESH_RADIAL
    mesh_axial: int = MESH_AXIAL
    numeric_only: bool = False


@dataclass(frozen=True)
class CalculationOutput:
    """Resultado completo; ``vol_res.is_success`` o ``res_2d.is_success`` indican fallos."""

    res_2d: NumericResult
    region: Region2D
    rec: MethodRecommendation | None
    vol_res: VolumeResult
    mesh: SolidMesh3D | None
    axis: RevolutionAxis
    chosen_method: SolidMethod | None


def _not_computed(method: SolidMethod | None, message: str) -> VolumeResult:
    return VolumeResult(method=method or SolidMethod.DISKS, is_success=False, error_message=message)


def _finite_mesh(mesh: SolidMesh3D) -> bool:
    grids = [mesh.x_outer, mesh.y_outer, mesh.z_outer]
    if mesh.x_inner is not None:
        grids += [mesh.x_inner, mesh.y_inner, mesh.z_inner]  # type: ignore[list-item]
    return all(g is not None and np.all(np.isfinite(g)) for g in grids)


def _fill_bad_rows(grid: np.ndarray | None) -> np.ndarray | None:
    """Interpola filas interiores no finitas desde sus vecinas (singularidad evitable aislada)."""
    if grid is None:
        return None
    out = np.array(grid, dtype=float)
    good = np.all(np.isfinite(out), axis=1)
    if good.all() or good.sum() < 2:
        return out
    rows = np.arange(out.shape[0])
    for col in range(out.shape[1]):
        out[~good, col] = np.interp(rows[~good], rows[good], out[good, col])
    return out


def _display_mesh(region: Region2D, request: CalculationRequest) -> SolidMesh3D | None:
    """Malla para el visor; nunca altera el cálculo del volumen.

    Si la función es infinita en un extremo (log x en 0) se recorta el intervalo una
    millonésima; si hay un punto interior aislado sin valor (sin(x)/x en 0) se interpola esa
    fila. Antes, una malla con NaN/Inf no se enviaba y el visor seguía mostrando el sólido del
    cálculo anterior.
    """
    mesh = generate_solid_mesh(region, request.axis, num_radial=request.mesh_radial, num_axial=request.mesh_axial)
    if not mesh.is_valid:
        return None
    if _finite_mesh(mesh):
        return mesh
    try:
        from integrallab.core.parser import parse_numeric_or_symbolic

        a = float(parse_numeric_or_symbolic(request.a_text).evalf())
        b = float(parse_numeric_or_symbolic(request.b_text).evalf())
        delta = 1e-6 * (b - a)
        nudged = generate_solid_mesh(
            replace(region, a=a + delta, b=b - delta), request.axis,
            num_radial=request.mesh_radial, num_axial=request.mesh_axial,
        )
        if nudged.is_valid:
            mesh = nudged
    except Exception:  # noqa: BLE001
        pass
    if _finite_mesh(mesh):
        return mesh
    mesh = replace(
        mesh,
        x_outer=_fill_bad_rows(mesh.x_outer), y_outer=_fill_bad_rows(mesh.y_outer), z_outer=_fill_bad_rows(mesh.z_outer),
        x_inner=_fill_bad_rows(mesh.x_inner), y_inner=_fill_bad_rows(mesh.y_inner), z_inner=_fill_bad_rows(mesh.z_inner),
    )
    return mesh if _finite_mesh(mesh) else None


def run_calculation(
    request: CalculationRequest,
    *,
    on_mesh: Callable[[SolidMesh3D], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> CalculationOutput:
    """Ejecuta el cálculo completo de la región descrita por ``request``.

    Args:
        request: Entradas ya parseadas.
        on_mesh: Se invoca con la malla 3D en cuanto existe (antes del volumen simbólico).
        is_cancelled: Se consulta entre pasos; si devuelve True se lanza ``CalculationCancelled``.

    Raises:
        CalculationCancelled: Si ``is_cancelled`` lo pide entre dos pasos.
    """

    def checkpoint() -> None:
        if is_cancelled is not None and is_cancelled():
            raise CalculationCancelled()

    region = Region2D(
        f_expr=request.f,
        g_expr=request.g,
        a=request.a_text,
        b=request.b_text,
        variable="x",
    )

    # Variables sin valor (a*x**2, x*y): antes se daba «éxito» con un volumen simbólico en
    # función de a, sin gráfica ni sólido.
    extra = sorted({*request.f.variables, *(request.g.variables if request.g is not None else [])} - {"x"})
    if extra:
        message = (
            f"La expresión usa símbolos sin valor: {', '.join(extra)}. Solo se admite la variable x "
            "(sustituya las constantes por números)."
        )
        return CalculationOutput(
            NumericResult(None, "", "", False, message), region, None, _not_computed(request.method, message),
            None, request.axis, request.method,
        )

    # Dominio: f y g deben ser reales en [a, b] (sqrt(x) en [-1, 1] daba ?rea compleja y V = 0).
    domain_msg = domain_error(region)
    if domain_msg:
        return CalculationOutput(
            NumericResult(None, "", "", False, domain_msg), region, None, _not_computed(request.method, domain_msg),
            None, request.axis, request.method,
        )

    checkpoint()
    axis_msg = axis_crossing_error(region, request.axis)
    if axis_msg:
        vol = _not_computed(
            request.method,
            f"{axis_msg} Elija un eje que no atraviese la regi?n (por ejemplo, uno que pase por "
            "su borde o fuera de ella).",
        )
        return CalculationOutput(
            NumericResult(None, "", "", False, vol.error_message), region, None, vol, None, request.axis, request.method
        )

    checkpoint()
    mesh = _display_mesh(region, request)
    if on_mesh is not None and mesh is not None:
        on_mesh(mesh)

    checkpoint()
    if request.numeric_only:
        import mpmath
        import sympy
        from integrallab.core.solids import _evaluate_bounds

        a, b, _, _ = _evaluate_bounds(region.a, region.b)
        var_sym = sympy.Symbol(region.variable)
        f_sym = request.f.sympy_expr
        g_sym = request.g.sympy_expr if request.g is not None else sympy.Integer(0)
        diff_sym = sympy.Abs(f_sym - g_sym)
        fn = sympy.lambdify(var_sym, diff_sym, modules="mpmath")
        area_val = float(mpmath.quad(fn, [a, b]))
        res_2d = NumericResult(
            value=area_val,
            exact_plain_text=f"{area_val:.5f}",
            exact_latex=f"{area_val:.5f}",
            is_success=True,
        )
        vol_val = numeric_volume(region, request.axis)
        method = request.method or (
            SolidMethod.SHELLS if request.axis.orientation == AxisOrientation.VERTICAL else SolidMethod.WASHERS
        )
        vol_res = VolumeResult(
            method=method,
            is_success=vol_val is not None,
            numeric_value=vol_val,
            exact_plain_text=f"{vol_val:.5f}" if vol_val is not None else "",
            exact_latex=f"{vol_val:.5f}" if vol_val is not None else "",
            steps=[],
            warnings=["C?lculo num?rico (sin forma exacta)."],
        )
        return CalculationOutput(res_2d, region, None, vol_res, mesh, request.axis, request.method)

    integrand = subtract_expressions(request.f, request.g) if request.g is not None else request.f
    res_2d = integrate_definite(integrand, request.a_text, request.b_text)
    if not res_2d.is_success:
        return CalculationOutput(
            res_2d, region, None, _not_computed(request.method, "No se calcul? el volumen."),
            None, request.axis, request.method,
        )

    checkpoint()
    rec = recommend_method(region, request.axis)
    checkpoint()
    vol_res = calculate_revolution_volume(region, request.axis, method=request.method)
    checkpoint()
    return CalculationOutput(res_2d, region, rec, vol_res, mesh, request.axis, request.method)


def serve_requests(
    conn: object,
    postprocess: Callable[[CalculationOutput], object] | None = None,
) -> None:
    """Bucle del proceso de cálculo: recibe ``(id, CalculationRequest)`` y responde por la tubería.

    Mensajes de salida: ``("mesh", id, SolidMesh3D)``, ``("assets", id, objeto)`` (si hay
    ``postprocess``, p. ej. fórmulas ya renderizadas), ``("done", id, CalculationOutput)`` y
    ``("error", id, texto)``. Termina al recibir ``None`` o al cerrarse la tubería (el proceso
    padre murió o canceló el trabajo).
    """
    while True:
        try:
            message = conn.recv()  # type: ignore[attr-defined]
        except (EOFError, OSError):
            return
        if message is None:
            return
        job_id, request = message
        try:
            output = run_calculation(
                request, on_mesh=lambda mesh: conn.send(("mesh", job_id, mesh))  # type: ignore[attr-defined]
            )
            if postprocess is not None:
                try:
                    conn.send(("assets", job_id, postprocess(output)))  # type: ignore[attr-defined]
                except (EOFError, OSError, BrokenPipeError):
                    raise
                except Exception:  # noqa: BLE001 - los extras son opcionales
                    pass
            conn.send(("done", job_id, output))  # type: ignore[attr-defined]
        except (EOFError, OSError, BrokenPipeError):
            return
        except Exception as exc:  # noqa: BLE001 - se informa al proceso padre
            try:
                conn.send(("error", job_id, f"{exc.__class__.__name__}: {exc}"))  # type: ignore[attr-defined]
            except (EOFError, OSError):
                return
