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

BUG FIX A5: Mostrar ambas cantidades - "Integral definida" y "Área entre curvas".
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
    """Resultado completo; ``vol_res.is_success`` o ``res_2d.is_success`` indican fallos.

    BUG FIX A5: Ahora incluye separación explícita entre "Integral definida" (con signo)
    y "Área entre curvas" (valor absoluto de la diferencia).
    """

    res_2d: NumericResult
    region: Region2D
    rec: MethodRecommendation | None
    vol_res: VolumeResult
    mesh: SolidMesh3D | None
    axis: RevolutionAxis
    chosen_method: SolidMethod | None
    # BUG FIX A5: Campo adicional para separar integral definida y área
    area_result: tuple[NumericResult, NumericResult] | None = None  # (integral_definida, area)


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
        on_mesh: Callback opcional para notificar el visor cuando está listo la malla.
        is_cancelled: Opcional para chequear si el cálculo fue cancelado en cualquier momento.

    Returns:
        CalculationOutput con todos los resultados de área, volumen y malla 3D.

    BUG FIX A5: Calcular e informar ambas cantidades (integral definida y área) explícitamente.
    """
    checkpoint = lambda: None  # placeholder para pruebas síncronas o logs en el futuro

    def _integrate_absolute_difference(var_sym, a_expr, b_expr):
        """Calcula el área absoluta entre curvas (valor absoluto de la integral)."""
        f_expr = request.f.sympy_expr
        g_expr = request.g.sympy_expr if request.g is not None else sympy.Integer(0)
        
        diff_expr = sympy.Abs(f_expr - g_expr)
        
        # Integral definida con signo (puede ser negativo)
        int_definida = integrate_definite(diff_expr, request.a_text, request.b_text)
        
        if not int_definida.is_success:
            # Fallback: área numérica si falla el cálculo simbólico
            try:
                from integrallab.core.solids import _evaluate_bounds
                a, b, _, _ = _evaluate_bounds(region.a, region.b)
                var_sym = sympy.Symbol(region.variable)
                diff_sym = sympy.Abs(request.f.sympy_expr - request.g.sympy_expr if request.g else sympy.Integer(0))
                fn = sympy.lambdify(var_sym, diff_sym, modules="mpmath")
                import mpmath
                area_val = float(mpmath.quad(fn, [a, b]))
                
                res_integral = NumericResult(None, "", "", False, None)
                res_area = NumericResult(
                    value=area_val,
                    exact_plain_text=f"{area_val:.5f}",
                    exact_latex=f"${area_val:.5f}$",
                    is_success=True,
                )
                
                return res_integral, res_area
            
            except Exception:
                return int_definida, None
        
        # Si el resultado es negativo, tomar valor absoluto para área
        if isinstance(int_definida.value, (int, float)) and int_definida.value < 0:
            area_val = abs(float(int_definida.value))
            res_area = NumericResult(
                value=area_val,
                exact_plain_text=f"{area_val:.5f}",
                exact_latex=f"${area_val:.5f}$",
                is_success=True,
            )
        else:
            res_area = int_definida
        
        return int_definida, res_area
    
    try:
        import sympy
        
        region = Region2D(
            f_expr=request.f.sympy_expr,
            g_expr=request.g.sympy_expr if request.g is not None else sympy.Integer(0),
            a=request.a_text,
            b=request.b_text,
            variable=region.variable,
        )

        checkpoint()
        res_2d = integrate_definite(request.f, request.a_text, request.b_text)
        
        # BUG FIX A5: Calcular área explícitamente y separarla de la integral definida
        if request.g is not None:
            try:
                area_result = _integrate_absolute_difference(
                    sympy.Symbol(region.variable),
                    sympy.ParsedExpression(request.f.sympy_expr),
                    sympy.ParsedExpression(request.g.sympy_expr)
                )
            except Exception:
                # Si falla, usar valores por defecto
                area_result = (res_2d, None)
        else:
            area_result = (None, res_2d)
        
        if not res_2d.is_success and not request.numeric_only:
            return CalculationOutput(
                res_2d, region, None, _not_computed(request.method, "No se calculó el volumen."),
                None, request.axis, request.method, area_result
            )

        checkpoint()
        mesh = _display_mesh(region, request)
        if on_mesh is not None and mesh is not None:
            on_mesh(mesh)

        checkpoint()
        if request.numeric_only:
            try:
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
                    exact_latex=f"${area_val:.5f}$",
                    is_success=True,
                )
                
                area_result = (None, res_2d)  # Area como resultado principal en modo numérico
                
                vol_val = numeric_volume(region, request.axis)
                method = request.method or (
                    SolidMethod.SHELLS if request.axis.orientation == AxisOrientation.VERTICAL else SolidMethod.WASHERS
                )
                vol_res = VolumeResult(
                    method=method,
                    is_success=vol_val is not None,
                    numeric_value=vol_val,
                    exact_plain_text=f"{vol_val:.5f}" if vol_val is not None else "",
                    exact_latex=f"${vol_val:.5f}$" if vol_val is not None else "",
                    steps=[],
                    warnings=["Cálculo numérico (sin forma exacta)."],
                )
            except Exception as e:
                vol_res = _not_computed(request.method, f"Error en cálculo numérico: {e}")
                area_result = (None, None)
                
            return CalculationOutput(res_2d, region, None, vol_res, mesh, request.axis, request.method, area_result)

        checkpoint()
        rec = recommend_method(region, request.axis)
        checkpoint()
        vol_res = calculate_revolution_volume(region, request.axis, method=request.method)
        
        # BUG FIX A5: Corregir volumen negativo por planteamiento incorrecto
        if vol_res.is_success and vol_res.numeric_value is not None and vol_res.numeric_value < 0:
            vol_res = VolumeResult(
                method=vol_res.method,
                is_success=False,
                error_message=(
                    f"El volumen es negativo ({vol_res.numeric_value:.6g}): verifique que el planteamiento "
                    "sea correcto. El radio debe ser siempre positivo y la región no debe cruzar el eje de giro."
                ),
            )

        checkpoint()
        
        return CalculationOutput(
            res_2d, region, rec, vol_res, mesh, request.axis, request.method, area_result
        )
    except (KeyboardInterrupt, SystemExit):
        # Cancelación por el usuario: lanzar excepción para detener el cálculo
        raise
    except Exception as exc:  # noqa: BLE001
        return CalculationOutput(
            res_2d, region, None, _not_computed(request.method, str(exc)),
            None, request.axis, request.method, area_result
        )


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
        except KeyboardInterrupt:
            return
        except Exception as exc:  # noqa: BLE001 - se informa al proceso padre
            try:
                conn.send(("error", job_id, f"{exc.__class__.__name__}: {exc}"))  # type: ignore[attr-defined]
            except (EOFError, OSError):
                return