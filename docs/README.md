# Documentación de IntegralLab

Índice de toda la documentación del proyecto, con el orden de lectura recomendado para personas y para asistentes de IA que trabajen sobre el código.

## Orden de lectura

1. [`../AGENTS.md`](../AGENTS.md): reglas de arquitectura, de trabajo, de seguridad, de privacidad y de autoría. Obligatorio antes de cambiar código.
2. [`ARQUITECTURA.md`](ARQUITECTURA.md): capas, módulos, modelo de procesos y flujo de un cálculo.
3. [`PROJECT_STATUS.md`](PROJECT_STATUS.md): qué está hecho, qué falta y la siguiente tarea.
4. [`AUDITORIA_2026-10-24.md`](AUDITORIA_2026-10-24.md): bugs conocidos (A1–A8, M1–M13) y el plan para corregirlos. Léala antes de tocar `core/solids.py`, el parser, los deslizadores o los reportes.
5. [`TECHNICAL_DECISIONS.md`](TECHNICAL_DECISIONS.md): por qué el proyecto es como es (D1–D7).
6. Documentos de cada función, según la tarea (tabla siguiente).
7. [`SESSION_LOG.md`](SESSION_LOG.md): historial de sesiones, solo si hace falta el contexto de un cambio antiguo.

## Mapa de documentos

| Documento | Contenido | Se actualiza |
| --- | --- | --- |
| [`../README.md`](../README.md) | Qué hace la aplicación, instalación, stack y estructura | Al cambiar funciones visibles o el stack |
| [`../AGENTS.md`](../AGENTS.md) | Reglas para personas y agentes de IA | Al cambiar reglas o la estructura |
| [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) | Componentes de terceros, versiones y licencias | Al añadir o actualizar un componente |
| [`../COPYRIGHT.md`](../COPYRIGHT.md), [`../LICENSE`](../LICENSE) | Autoría y licencia | Solo con autorización del autor |
| [`ARQUITECTURA.md`](ARQUITECTURA.md) | Arquitectura actual | Al mover responsabilidades entre módulos |
| [`PROJECT_STATUS.md`](PROJECT_STATUS.md) | Estado por fases y pendientes | Al terminar cada sesión |
| [`SESSION_LOG.md`](SESSION_LOG.md) | Registro de sesiones (solo se anexa) | Al terminar cada sesión |
| [`TECHNICAL_DECISIONS.md`](TECHNICAL_DECISIONS.md) | Decisiones de diseño (solo se anexa) | Al tomar una decisión de arquitectura |
| [`AUDITORIA_2026-10-24.md`](AUDITORIA_2026-10-24.md) | Auditoría técnica completa y plan de acción | Al corregir un hallazgo, anotarlo en `PROJECT_STATUS.md` |
| [`EDITOR_VISUAL.md`](EDITOR_VISUAL.md) | Editor visual de fórmulas: uso, diseño, pruebas y mantenimiento | Al cambiar el editor o actualizar MathLive |
| [`PRIVACIDAD.md`](PRIVACIDAD.md) | Qué datos no entran al repositorio y cómo se comprueba | Al cambiar las reglas de privacidad |
| [`PRUEBAS_PROTOTIPO_THREEJS.md`](PRUEBAS_PROTOTIPO_THREEJS.md) | Pruebas del prototipo del visor Three.js | Histórico |
| [`archive/`](archive/) | Informes anteriores de la integración de Three.js y la fase 12 | Histórico, no se edita |
| [`img/`](img/) | Capturas de la aplicación usadas en la documentación | Al cambiar la interfaz |

## Convenciones de la documentación

- Idioma: español (Colombia), igual que la interfaz y los docstrings.
- Rutas siempre relativas a la raíz del repositorio (`integrallab/core/parser.py`), nunca absolutas.
- Sin datos personales: solo el nombre del autor en los avisos de autoría (ver [`PRIVACIDAD.md`](PRIVACIDAD.md)). `tests/test_privacy.py` lo comprueba.
- Las cifras de pruebas y versiones se toman de una ejecución real de `pytest`, con su fecha.
- Los documentos marcados «solo se anexa» no se reescriben: se añaden entradas al final.
