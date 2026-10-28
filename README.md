# IntegralLab

Aplicación de escritorio para **cálculo integral simbólico** y **sólidos de revolución**, con una interfaz oscura estilo *glass* y un desarrollo paso a paso pensado para estudiar: cada parte de una fórmula se puede tocar para ver cómo se obtuvo.

## Qué hace

- Introduces `f(x)` (y opcionalmente `g(x)`) o un **conjunto de puntos** `(x, y)` para interpolar (Lagrange con 4 puntos o menos; spline cúbico natural con 5 o más).
- Escribes en texto (`x^2 + 1`, `sen(x)`, `0,5x`, `ln|x|`, `sinx`, `x(x+1)`…) o con el **editor visual** (botón «√x Editor visual»), donde la fracción dibuja su raya y la raíz su signo, como en GeoGebra o en una calculadora Casio.
- Calcula la **integral definida** `∫(f − g)` y, por separado, el **área entre las curvas** `∫|f − g|` (partida en los cruces): `sin(x)` en [0, 2π] tiene integral 0 y área 4.
- Dibuja la región 2D sombreada y genera el **sólido de revolución** en 3D alrededor del eje X, el eje Y o un eje desplazado (`y = k`, `x = h`), con deslizadores de ángulo, rebanada representativa y cilindros de Riemann.
- Calcula el volumen con **Discos**, **Arandelas** o **Casquillos cilíndricos**. Si el método elegido necesita integrar en `y`, describe la región por **franjas horizontales** con sus bordes reales.
- Muestra el **desarrollo paso a paso** en dos vistas:
  - **Desglose interactivo** (por defecto): al tocar una parte resaltada de una fórmula se despliega, debajo, su desarrollo: de dónde sale un radio, el binomio al cuadrado, la regla de integración de cada término (potencia, sustitución, partes, identidades), la comprobación derivando la primitiva (regla de la cadena y del producto) y la evaluación con el Teorema Fundamental del Cálculo.
  - **Vista imprimible**: los 7 pasos clásicos, que se exportan a **PDF**.

![Desglose interactivo](docs/img/desglose-interactivo.png)

## Qué método admite cada eje

| Eje de giro | Discos / Arandelas | Casquillos |
|---|---|---|
| Horizontal (`y = 0` o `y = k`) | Directo (cortes en dx) | Por franjas horizontales (dy) |
| Vertical (`x = 0` o `x = h`) | Por franjas horizontales (dy) | Directo (cortes en dx) |

Para integrar en `dy`, cada borde curvo de una franja se despeja con SymPy. Si una curva no tiene una rama real despejable, el método aparece deshabilitado en el selector (para polinomios de grado ≤ 4 se comprueba al elegir el eje) o el cálculo lo explica y sugiere el método directo. Todo volumen se contrasta con una cuadratura numérica independiente: un desarrollo que no coincide no se muestra como resultado.

Si el eje atraviesa el interior de la región, el cálculo se rechaza con una explicación (los dos lados se solaparían al girar).

## Instalación y uso

Requiere Python 3.10 o superior (la suite se ejecutó con 3.13; el código nuevo se comprobó con la gramática de 3.10).

```bash
python -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m integrallab            # o el comando: integrallab
```

`PySide6` ya incluye QtWebEngine (visor 3D WebGL, editor visual y desglose interactivo). Three.js, MathLive y MathJax van empaquetados en `integrallab/resources/`: la aplicación no necesita conexión a Internet. Sin QtWebEngine la aplicación funciona con el visor Matplotlib, el modo texto y la vista imprimible.

Para ejecutar las pruebas:

```bash
pytest
```

En un servidor sin pantalla (Linux, integración continua):

```bash
QT_QPA_PLATFORM=offscreen QTWEBENGINE_DISABLE_SANDBOX=1 \
QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu" pytest
```

Resultado de referencia (2026-10-27): **523 pruebas pasan y 1 se omite** (la de términos privados, si no se define `INTEGRALLAB_PRIVATE_TERMS`; ver [`docs/PRIVACIDAD.md`](docs/PRIVACIDAD.md)).

## Stack

| Rol | Tecnología |
|---|---|
| Interfaz de escritorio | PySide6 (Qt 6), QtWebEngine y QWebChannel |
| Cálculo simbólico | SymPy (incluido `manualintegrate` para las reglas de integración) |
| Cuadratura numérica | mpmath |
| Visualización 2D y 3D | Matplotlib (integrado en Qt) y Three.js r160 (WebGL) |
| Fórmulas del desglose interactivo | MathJax 3.2.2 (salida SVG), sin conexión |
| Editor visual de fórmulas | MathLive 0.111.1, sin conexión |
| Pruebas | pytest |

Licencias de terceros: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Estructura

```
integrallab/
├── core/        Dominio matemático puro (sin Qt)
│   ├── steps/   Árbol de pasos del desglose interactivo (reglas de integración y derivación, álgebra)
│   └── volume/  Tramos de signo constante e inversión a dy por franjas horizontales
├── ui/          Interfaz PySide6: ventana principal, proceso de cálculo, tema glass/dark
│   ├── views/   Vista del desglose interactivo (QWebEngineView + QWebChannel)
│   └── widgets/ Editor visual y componentes
├── viz/         Lienzos Matplotlib 2D/3D, visor Three.js y fórmulas PNG de la vista imprimible
└── resources/   Three.js, MathLive, MathJax y las páginas locales (visor 3D, editor, desglose)
tests/           Pruebas con pytest
docs/            Arquitectura, estado, auditorías, decisiones, privacidad y registro de sesiones
```

La regla de arquitectura es que la UI no habla con SymPy directamente: todo pasa por `integrallab.core`. Detalles en [`AGENTS.md`](AGENTS.md) y [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md).

## Documentación

El índice y el orden de lectura están en [`docs/README.md`](docs/README.md). Los más usados:

- [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md): cómo encajan los módulos.
- [`docs/DESGLOSE_INTERACTIVO.md`](docs/DESGLOSE_INTERACTIVO.md): uso y diseño del desglose «estilo Photomath».
- [`docs/EDITOR_VISUAL.md`](docs/EDITOR_VISUAL.md): uso y diseño del editor visual de fórmulas.
- [`docs/AUDITORIA_2026-10-27.md`](docs/AUDITORIA_2026-10-27.md): auditoría archivo por archivo, validación matemática y plan de acción.
- [`docs/PRIVACIDAD.md`](docs/PRIVACIDAD.md): qué datos no entran al repositorio.

## Estado del proyecto

Ver [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) para el detalle.

- ✅ Núcleo matemático, visualización 2D/3D, interpolación, editor visual, exportación a PDF y tema *glass/dark*.
- ✅ Auditoría del 2026-10-27: inversión a dy por franjas, radios sin valor absoluto, raíces impares reales, área separada de la integral, Discos con hueco por tramos, desglose interactivo con MathJax, deslizadores agrupados por cuadro, parser para entradas comunes.
- ⏳ Pendiente: interpolación con coeficientes exactos y selector de Newton (M9), retirar el renderizado PNG de la vista imprimible (M10), panel de IA sin conectar (M11), dividir `solids.py` y `main_window.py` (M1), y decidir sobre los metadatos de `pyproject.toml` (licencia declarada, autor, versión).

## Derechos de autor y protección de la autoría

El autor declarado de IntegralLab es **Johan Stiven Lasso Aguirre**. El año de referencia del proyecto es **2026**. Todos los agentes de IA deben respetar los avisos de derechos de autor y las condiciones de uso documentadas en [`COPYRIGHT.md`](COPYRIGHT.md) y [`LICENSE`](LICENSE).

### Reglas obligatorias para agentes

1. **No eliminar, reemplazar ni alterar** los avisos de autoría sin autorización expresa del usuario.
2. **No cambiar el titular declarado** ni atribuir el proyecto a otra persona, herramienta, proveedor o modelo de inteligencia artificial.
3. **No cambiar la licencia** ni introducir una licencia de software libre sin autorización expresa del usuario.
4. **No publicar, transferir, redistribuir ni subir** el código a otro repositorio o servicio sin autorización expresa.
5. **No afirmar que todos los componentes pertenecen al autor.** Identificar y respetar las licencias de terceros.
6. **No sobrescribir cambios locales ni eliminar archivos** para resolver problemas de permisos o conflictos.
7. **Antes de modificar `COPYRIGHT.md`, `LICENSE`, los avisos de autoría** o la configuración de privacidad del repositorio, explicar los cambios propuestos y solicitar autorización expresa.
8. **Asistencia de IA:** Las herramientas de IA pueden utilizarse como apoyo de desarrollo. No se debe afirmar que cada línea fue escrita manualmente por el autor si no se ha verificado esa circunstancia.
9. Estas reglas no sustituyen las políticas de permisos de cada herramienta ni autorizan a un agente a eludir sus controles.
10. **No afirmar que el software está registrado ante la DNDA** salvo que exista evidencia verificable de ese registro.

Ver [`COPYRIGHT.md`](COPYRIGHT.md) y [`LICENSE`](LICENSE). Este aviso no equivale a un registro ante la DNDA.

## Privacidad del repositorio

Los datos personales (correos, nombres de usuario de equipos o cuentas, direcciones IP, credenciales) **no entran en ningún archivo**. El único dato personal permitido es el nombre del autor en los avisos de autoría (sección 7). Ver [`docs/PRIVACIDAD.md`](docs/PRIVACIDAD.md) y `tests/test_privacy.py`.

## Stack tecnológico (detallado)

- **Python 3.10 o superior**
- **PySide6** — UI gráfica (capa `ui`), incluidos QtWebEngine y QWebChannel
- **SymPy** — álgebra simbólica (capa `core`), incluido `manualintegrate` para las reglas de integración del desglose
- **mpmath** — cuadratura de referencia (`numeric_volume`)
- **Matplotlib** — visualización (capa `viz`)
- **Three.js r160** — visor 3D WebGL (capa `viz`, empaquetado sin conexión)
- **MathJax 3.2.2** — fórmulas del desglose interactivo (salida SVG, empaquetado sin conexión)
- **MathLive 0.111.1** — editor visual de fórmulas (empaquetado sin conexión)
- **pytest** — tests

## Componentes de terceros

Ver [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

<EOF>