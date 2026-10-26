# Privacidad del repositorio

El único dato personal que debe aparecer en IntegralLab es el nombre del autor, **Johan Stiven Lasso Aguirre**, en los avisos de autoría (`README.md`, `COPYRIGHT.md`, `LICENSE`, `AGENTS.md`). Nada más que identifique a una persona o a su equipo debe entrar al repositorio: ni en el código, ni en la documentación, ni en los registros de sesión.

## Qué no se escribe nunca

| Dato | Ejemplo de lo que NO va | Qué escribir en su lugar |
| --- | --- | --- |
| Correos electrónicos | `<nombre>@<dominio>` | Nada, o `usuario@example.com` en ejemplos |
| Rutas absolutas de una carpeta personal | `C:\Users\<usuario>\...`, `/home/<usuario>/...` | Rutas relativas a la raíz del repositorio, o `<carpeta-del-repositorio>` |
| Nombres de usuario del equipo o de cuentas | Usuario de Windows, de GitHub o de otros servicios | Nada |
| Nombres de equipo, direcciones IP, redes | `DESKTOP-XXXX`, `192.168.x.x` | Nada |
| Claves, tokens, contraseñas | Claves de API | Variables de entorno fuera del repositorio |
| Capturas de pantalla con datos personales | Barra de tareas, explorador de archivos, correo abierto | Capturas solo de la ventana de la aplicación |

Sí se puede registrar el entorno técnico de las pruebas: sistema operativo, versión de Python y de cada biblioteca.

## Limpieza del 24 de octubre de 2026

Se eliminaron datos personales de la documentación. Los valores no se repiten aquí:

| Archivo | Qué se quitó | Cómo quedó |
| --- | --- | --- |
| `docs/SESSION_LOG.md` | Ruta local con el nombre de usuario del equipo (25 líneas de «Entorno» y una confirmación de `Get-Location`) | «Windows · Python …» sin ruta |
| `docs/PROJECT_STATUS.md` | Fila «Ruta absoluta del proyecto» | Fila eliminada |
| `docs/PRUEBAS_PROTOTIPO_THREEJS.md` | Comando `cd` con la ruta local; URL con el usuario de GitHub | `cd "<carpeta-del-repositorio>"`; «IntegralLab (repositorio del proyecto)» |
| `integrallab/viz/experimental/README.md` | Comando `cd` con la ruta local | `cd "<carpeta-del-repositorio>"` |
| `docs/archive/INFORME_EJECUTIVO_THREEJS.md` | 6 enlaces con la ruta local; 2 URL con el usuario de GitHub | Enlaces relativos; nombre del proyecto |
| `docs/archive/AUDITORIA_VIZUALIZACION_3D.md`, `EVALUACION_TECNICA_THREEJS.md` | URL con el usuario de GitHub | Nombre del proyecto |

`SESSION_LOG.md` es un registro de solo anexar; esta es la única edición de entradas antiguas y solo quitó esos datos.

## Comprobación automática

`tests/test_privacy.py` revisa todos los archivos de texto del proyecto (salvo el código de terceros de `resources/js/` y `resources/mathlive/`) y falla si encuentra:

- un correo electrónico (se permiten `example.com` y las direcciones `noreply` de GitHub);
- una ruta absoluta de carpeta personal en Windows, Linux o macOS;
- un enlace a un repositorio de GitHub de una cuenta que no sea de un componente de terceros declarado.

El informe de la prueba indica archivo y línea, nunca el dato encontrado.

Para buscar además términos propios (usuario del equipo, usuario de GitHub, correo) sin escribirlos en el repositorio, páselos solo al ejecutar:

```powershell
# PowerShell
$env:INTEGRALLAB_PRIVATE_TERMS = "termino1,termino2,termino3"
pytest tests/test_privacy.py
```

```bash
# Bash
INTEGRALLAB_PRIVATE_TERMS="termino1,termino2,termino3" pytest tests/test_privacy.py
```

## Lo que la limpieza de archivos no alcanza

### Metadatos de los commits

Cada commit guarda el nombre y el correo configurados en Git. Para que los próximos commits no muestren un correo personal:

1. En GitHub, activar *Settings → Emails → Keep my email addresses private* (y, si se desea, *Block command line pushes that expose my email*).
2. Configurar el repositorio con el nombre del autor y la dirección privada que muestra GitHub en esa misma página:

```bash
git config user.name "Johan Stiven Lasso Aguirre"
git config user.email "<ID>+<usuario>@users.noreply.github.com"
```

### Historial

Un commit nuevo que borra un dato no lo quita de los commits anteriores. Mientras el repositorio sea público en GitHub, las versiones antiguas de los documentos y el correo de los commits siguen visibles. Antes de anunciar el proyecto como código abierto hay dos caminos:

- **Empezar un repositorio nuevo** con un único commit inicial hecho desde el árbol ya limpio y con la configuración de Git anterior. Es lo más simple y lo más seguro.
- **Reescribir el historial** con [git filter-repo](https://github.com/newren/git-filter-repo): `--replace-text` con un archivo de expresiones guardado FUERA del repositorio, y `--mailmap` para el autor de los commits; después, `git push --force`. Es destructivo: hacer antes una copia completa. Las copias y bifurcaciones que otras personas ya tengan conservan el historial anterior.

### El parche

Un archivo `.patch` contiene también las líneas que elimina, así que el parche de esta limpieza incluye los datos que quita. Úselo solo para aplicarlo en su copia local y no lo publique; para compartir los archivos finales use el `.zip` o el repositorio ya limpio.

## Antes de publicar como código abierto

- [ ] `pytest` completo en verde, incluido `tests/test_privacy.py` con `INTEGRALLAB_PRIVATE_TERMS` definido.
- [ ] Historial limpio (repositorio nuevo o reescrito) y correo privado configurado en Git.
- [ ] Decidir la licencia. Hoy el proyecto es de todos los derechos reservados (`LICENSE`, `COPYRIGHT.md`); cambiarla es decisión del autor (`AGENTS.md`, sección 7).
- [ ] Revisar `THIRD_PARTY_NOTICES.md` contra las versiones empaquetadas.
- [ ] Revisar capturas de pantalla nuevas en `docs/img/`: solo la ventana de la aplicación, sin metadatos.
