# IntegralLab

Aplicación de escritorio para **cálculo integral simbólico** y **sólidos de revolución**, con una interfaz oscura estilo *glass* y desarrollo paso a paso pensado para estudiar.

## Qué hace

- Introduces `f(x)` (y opcionalmente `g(x)`) o un **conjunto de puntos discretos** `(x, y)` para interpolación numérica.
- Puedes escribir las fórmulas en texto o activar el **editor visual** (botón «√x Editor visual»): la fracción dibuja su raya, la raíz su signo y la potencia su exponente, como en GeoGebra o en una calculadora Casio.
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
| Visualización 2D y 3D | Matplotlib (integrado en Qt) y Three.js (WebGL, QtWebEngine) |
| Editor visual de fórmulas | MathLive (MIT), sin conexión, en QtWebEngine |
| Tests | pytest |

## Estructura

```
integrallab/
├── core/       Dominio matemático puro: parser, editor visual (LaTeX → texto), integrales, muestreo y sólidos
├── ui/         Interfaz PySide6: ventana principal, proceso de cálculo, tema glass/dark y widgets
│   └── widgets/
├── viz/        Lienzos Matplotlib 2D/3D, visor Three.js y renderizado de LaTeX
└── resources/  Three.js, MathLive y las páginas locales del visor 3D y del editor visual
tests/          Pruebas con pytest
docs/           Arquitectura, estado, auditoría, decisiones, privacidad y registro de sesiones
```

La regla de arquitectura es que la UI nunca habla con SymPy directamente: todo pasa por `integrallab.core`. Detalles en `AGENTS.md` y `docs/ARQUITECTURA.md`.

## Documentación

El índice y el orden de lectura están en [`docs/README.md`](docs/README.md). Los más usados:

- [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md): cómo encajan los módulos.
- [`docs/EDITOR_VISUAL.md`](docs/EDITOR_VISUAL.md): uso y diseño del editor visual de fórmulas.
- [`docs/AUDITORIA_2026-10-24.md`](docs/AUDITORIA_2026-10-24.md): bugs conocidos y plan de corrección.
- [`docs/PRIVACIDAD.md`](docs/PRIVACIDAD.md): qué datos no entran al repositorio.
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md): componentes de terceros y sus licencias.

## Estado del proyecto

Ver `docs/PROJECT_STATUS.md` para el detalle por fases.

- ✅ Fases 1–11.2: núcleo matemático, visualización 2D/3D, desarrollo paso a paso, exportación a PDF y rediseño *glass/dark*.
- ✅ Fase 12: interpolación numérica (Lagrange, Newton, splines cúbicos), entrada de puntos discretos, visor 3D Three.js acelerado por WebGL y blindaje de seguridad matemática (174 pruebas pasando al 100%).
- ✅ Editor visual de fórmulas (estilo GeoGebra / calculadora Casio) y documentación completa con comprobación automática de privacidad (413 pruebas pasando; 1 se omite si no se define `INTEGRALLAB_PRIVATE_TERMS`).
- ⏳ Pendiente: corregir los hallazgos de la auditoría del 2026-10-24 (`docs/AUDITORIA_2026-10-24.md`).
- ⏳ Pendiente: conectar el panel de IA (`ChatPanel`), que hoy no tiene backend.

## Derechos de autor

IntegralLab es un proyecto de software desarrollado por **Johan Stiven Lasso Aguirre**.

**© 2026 Johan Stiven Lasso Aguirre. Todos los derechos reservados.**

El código original y la documentación propia están sujetos a los derechos de autor aplicables. No se autoriza su reutilización, modificación o distribución sin el permiso correspondiente, salvo en los casos permitidos por la legislación aplicable. Los componentes de terceros conservan sus respectivas licencias.

Para consultar el alcance del aviso de autoría y las condiciones de uso, revisa [`COPYRIGHT.md`](COPYRIGHT.md) y [`LICENSE`](LICENSE). Este aviso no equivale a un registro ante la DNDA.

