# IntegralLab

Aplicación de escritorio para **cálculo integral simbólico** y **sólidos de revolución**, con una interfaz oscura estilo *glass* y desarrollo paso a paso pensado para estudiar.

## Qué hace

- Introduces `f(x)` (y opcionalmente `g(x)`) o un **conjunto de puntos discretos** `(x, y)` para interpolación numérica.
- Soporta **Interpolación de Lagrange, Newton (diferencias divididas) y Splines Cúbicos naturales**.
- Calcula la integral definida de forma simbólica (resultado exacto y aproximado).
- Dibuja la región 2D sombreada entre las curvas.
- Genera el **sólido de revolución** en 3D alrededor del eje X, el eje Y o un eje desplazado (`y = k`, `x = h`).
- Calcula el volumen con **Discos**, **Arandelas** o **Casquillos cilíndricos**, con **despeje analítico automático a dy** cuando el método lo requiere.
- Muestra el **desarrollo analítico paso a paso** con fórmulas LaTeX renderizadas y lo exporta a **PDF**.

### Qué método admite cada eje

El sistema determina la compatibilidad geométrica de cortes y soporta **despeje analítico automático a dy** mediante SymPy:

| Eje de giro | Discos / Arandelas | Casquillos |
|---|---|---|
| Horizontal (`y = 0` o `y = k`) | ✅ Directo (dx) | ✅ Con inversión analítica (dy) |
| Vertical (`x = 0` o `x = h`) | ✅ Con inversión analítica (dy) | ✅ Directo (dx) |

Si una función no es invertible analíticamente, el selector lo indicará en el tooltip.

## Instalación y uso

Requiere Python 3.10 o superior (el proyecto se desarrolla con 3.14).

```bash
python -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m integrallab
```

Para ejecutar las pruebas:

```bash
pytest
```

## Stack

| Rol | Tecnología |
|---|---|
| Interfaz de escritorio | PySide6 (Qt) |
| Cálculo simbólico | SymPy |
| Visualización 2D y 3D | Matplotlib (integrado en Qt) |
| Tests | pytest |

## Estructura

```
integrallab/
├── core/    Dominio matemático puro: parser, integrales, muestreo y sólidos de revolución
├── ui/      Interfaz PySide6: ventana principal, tema glass/dark y widgets
│   └── widgets/
└── viz/     Lienzos Matplotlib 2D/3D, estilo y renderizado de LaTeX
tests/       Pruebas con pytest
docs/        Estado del proyecto, decisiones técnicas y registro de sesiones
```

La regla de arquitectura es que la UI nunca habla con SymPy directamente: todo pasa por `integrallab.core`. Detalles en `AGENTS.md` y `docs/TECHNICAL_DECISIONS.md`.

## Estado del proyecto

Ver `docs/PROJECT_STATUS.md` para el detalle por fases.

- ✅ Fases 1–11.2: núcleo matemático, visualización 2D/3D, desarrollo paso a paso, exportación a PDF y rediseño *glass/dark*.
- ✅ Fase 12: interpolación numérica (Lagrange, Newton, splines cúbicos), entrada de puntos discretos, visor 3D Three.js acelerado por WebGL y blindaje de seguridad matemática (174 pruebas pasando al 100%).
- ⏳ Pendiente: conectar el panel de IA (`ChatPanel`), que hoy no tiene backend.

## Derechos de autor

IntegralLab es un proyecto de software desarrollado por **Johan Stiven Lasso Aguirre**.

**© 2026 Johan Stiven Lasso Aguirre. Todos los derechos reservados.**

El código original y la documentación propia están sujetos a los derechos de autor aplicables. No se autoriza su reutilización, modificación o distribución sin el permiso correspondiente, salvo en los casos permitidos por la legislación aplicable. Los componentes de terceros conservan sus respectivas licencias.

Para consultar el alcance del aviso de autoría y las condiciones de uso, revisa [`COPYRIGHT.md`](COPYRIGHT.md) y [`LICENSE`](LICENSE). Este aviso no equivale a un registro ante la DNDA.

