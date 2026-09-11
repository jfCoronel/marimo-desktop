# NOTES — contexto del proyecto

Notas de diseño y decisiones que no se deducen del código. El *cómo* está en
[`README.md`](README.md); esto es el *por qué* y el estado.

Última actualización: 2026-09-11 (sesión 4).

---

## Objetivo

Un equivalente a `jupyter-desktop` **para [marimo](https://github.com/marimo-team/marimo)**:
una app de escritorio que trae su propio Python + marimo, de forma que el usuario
final no instala nada (ni Python, ni `uv`, ni un venv).

No existe nada equivalente: la org `marimo-team` no tiene `marimo-desktop`; hay
`marimo-jupyter-extension` y `jetbrains-marimo` (PoC), pero ninguna app standalone
con Python embebido. Lo más cercano hoy es `uvx marimo edit`, que aún exige `uv`.

## Estado actual (v1, verificado)

- **Ventana de control Tk** (`gui.py`): selector de carpeta + `Recent ▾`
  (hasta 8 carpetas de trabajo, en `config.json` → `recent_folders`), botón
  Start/Stop, URL clicable (abre el navegador por defecto) + botón Copy
  URL. No se abre ningún navegador automáticamente al arrancar. Cerrar la
  ventana para el servidor.
- **Modo `--headless`** (`launcher.py`): arranca servidor, abre navegador, bloquea.
  Para automatización. `--run` = modo app (`marimo run`).
- `MarimoServer` (`server.py`) gestiona el subproceso `marimo edit --headless
  --no-token` en un puerto libre de `127.0.0.1`; polling no bloqueante.
- Carpeta de notebooks: `./notebooks` en checkout de desarrollo; `~/marimo
  notebooks` (sembrada con los ejemplos) en la app empaquetada; override con
  `MARIMO_DESKTOP_NOTEBOOKS` o eligiéndola en la ventana.
- Empaquetado con **ux-py** (`ux bundle --format app`) → `dist/marimo-desktop.app`
  funcionando de punta a punta (probado también lanzando desde Finder).

## Decisiones de arquitectura

### Ventana Tk nativa en vez de pywebview

El plan original preveía envolver el servidor de marimo con `pywebview`. Se
descartó a favor de una **ventanita de control** que abre marimo en un navegador
real:

- El editor de marimo es pesado y rinde mejor en un navegador de verdad
  (devtools, extensiones, sesión). Meterlo en un webview añade fallos posibles
  (websockets, CSP, diálogos de archivo) sin ganar nada.
- La ventana se convierte en un panel de control persistente (carpeta,
  arrancar/parar, y en fase 2 crear/abrir notebooks).
- Ciclo de vida limpio: cerrar la ventana = parar el servidor.
- **Tkinter ya viene dentro del Python que empaqueta ux** (Tk 9.0) → cero
  dependencias nuevas, el `.app` sigue en ~21 MB.
- Coste aceptado: dos superficies (ventana + pestaña del navegador) en vez de una
  app unificada. Para una herramienta de notebooks es lo normal.
- Alternativa si algún día se quiere algo más discreto en Mac: `rumps` (app de
  barra de menú), pero es solo-Mac. Tk mantiene el camino multiplataforma.

### Sin selector de navegador ni apertura automática

Se quitó el desplegable "Navegador" y el auto-abrir al arrancar el servidor.
Ahora la ventana solo muestra el enlace clicable (abre el navegador por
defecto del sistema) y un botón "Copy URL":

- El desplegable dependía de `browsers._detected()` (rutas de `.app` en macOS,
  binarios en Linux) — código frágil y sin mantenimiento visible más allá del
  caso feliz. Se eliminó de `browsers.py`, que ahora es un `webbrowser.open`
  de una línea.
- Abrir automáticamente en un navegador "elegido" que a veces no era el que el
  usuario quería usar en ese momento era más sorpresa que ayuda. Con el enlace
  + copiar, el usuario decide: clic → por defecto, copiar → pegar en
  cualquier otro navegador manualmente.
- `--headless` (`launcher.py`) no se tocó: sigue abriendo el navegador por
  defecto automáticamente, porque ahí no hay ventana desde la que hacer clic.

### Fase 2 (Nuevo/Abrir/Recientes de ficheros) construida y luego revertida

En la sesión 2 se construyó `Nuevo notebook…` / `Abrir notebook…` /
`Recientes ▾` en la ventana Tk — cada acción abría su propio `MarimoServer`
de un solo fichero, independiente del servidor de Start/Stop — a pesar
de que ya se sabía que marimo resuelve exactamente eso por su cuenta: al
arrancar `marimo edit <carpeta>` (lo que ya hace Start/Stop), marimo
activa internamente su `DirectoryWorkspace`
(`_server/workspace/_directory.py`) y expone endpoints propios
(`_server/api/endpoints/home.py`: `/workspace_files`, `/recent_files`,
`/running_notebooks`) que alimentan una página de inicio en el navegador con
listado de notebooks, creación de nuevos y recientes.

**Revertido en sesión 4**, a petición del usuario tras confirmar que la
redundancia con la home page de marimo no merecía la pena: se quitaron los
tres controles y toda la infraestructura de sesiones sueltas
(`_extra_servers`, `_pending`, `_poll_pending`, `_open_file`). En su lugar,
`Recent ▾` ahora recuerda **carpetas de trabajo** (`config.json` →
`recent_folders`, hasta 8), no ficheros — un complemento directo del
selector de carpeta ya existente, sin tocar cómo se abren los notebooks
(eso sigue siendo cosa de la home page de marimo). Deshabilitado junto con
`Change…` mientras el servidor corre, por la misma razón de siempre:
cambiar la carpeta no tiene efecto hasta el próximo arranque.

### Icono de la app

`assets/icon.png` (1024×1024) es arte original generado con un script Pillow
ad hoc (no guardado en el repo, solo la imagen resultante).

Primera versión (sesión 2): una bola de musgo verde con sombreado esférico y
textura de "pelusa", sobre fondo teal→azul degradado.

**Rehecho en sesión 4**: el usuario mandó una imagen de referencia (anillo
tipo pincel + "m") que tiene toda la pinta de ser el logo oficial de marimo.
Usarlo tal cual en el icono de una app no oficial podría leerse como
afiliación/respaldo que no existe, así que se hizo una versión **inspirada,
no copiada**: mismo lenguaje visual (anillo circular abierto arriba, con un
pequeño remate tipo trazo de pincel, envolviendo una "m" en negrita) pero
trazo, tipografía y fondo propios (teal `#0f7a6e` sobre blanco cálido, no el
tono/fondo exactos de marimo). El primer intento con muchos segmentos de
línea salió en "dientes de sierra" (los extremos de cada segmento no
casan); se corrigió dibujando el anillo como **un solo polígono** con radio
interior/exterior variando suavemente por ángulo (así el trazo es
continuo por construcción, sin uniones visibles).

- `pyproject.toml` → `[tool.ux.macos] icon = "assets/icon.png"`: ux lo
  convierte a `.icns` él mismo (`sips`/`iconutil`) al hacer `ux bundle`;
  confirmado en `Info.plist` (`CFBundleIconFile = AppIcon`) y
  `Contents/Resources/AppIcon.icns` tras reconstruir.
- También referenciado en `[tool.briefcase.app.marimo-desktop] icon =
  "assets/icon"` (sin extensión, como espera Briefcase) para que el plan B
  no se quede sin icono si algún día se usa.
- **Nombre en el Dock**: ya estaba resuelto — `CFBundleName = "marimo
  desktop"` (de `bundle_name` en `[tool.ux.macos]`) ya aparecía correcto en
  el `Info.plist` desde antes de esta sesión; no hizo falta tocarlo.
- Para regenerar/ajustar el icono basta rehacer el mismo tipo de script con
  Pillow (`uv run --with pillow --with numpy python …`) sin añadir Pillow
  como dependencia del proyecto — es una herramienta de un solo uso, no algo
  que la app necesite en tiempo de ejecución.
- **Con `uv run marimo-desktop` no se ve** (sesión 3): el icono vive en
  `Info.plist`/`AppIcon.icns`, que solo existen dentro de un bundle `.app`.
  Corriendo el script suelto, macOS pone en el Dock el icono genérico del
  intérprete de Python — es inherente a no empaquetar, no un fallo de la
  configuración. Poner un icono también en modo dev requeriría PyObjC
  (`NSApplication.setApplicationIconImage_`) solo para eso; se descartó por
  ahora para no añadir una dependencia de packaging al proyecto por algo
  puramente cosmético del flujo de desarrollo.

### Pie de página: versiones + copyright

A petición del usuario (sesión 4): la ventana muestra Python/`uv`/marimo en
uso y `© 2026 jfCoronel`. Detalles no obvios:

- `uv` no está garantizado en el `PATH` dentro del `.app` empaquetado (ux
  embebe su propio `uv` en otro sitio), así que en vez de invocar `uv
  --version` como subproceso, se lee directamente `sys.prefix/pyvenv.cfg`
  — `uv` siempre escribe su propia versión ahí (`uv = 0.12.13`) al crear el
  venv. Verificado que da el valor correcto tanto en el `.venv` de
  desarrollo como en el del bundle.
- La versión de marimo se lee con `importlib.metadata.version("marimo")`,
  no con `import marimo; marimo.__version__` — evita cargar el paquete
  completo (bastante pesado) solo para leer un string, así que no añade
  nada perceptible al arranque de la ventana.

### ux-py como empaquetador (con Briefcase de reserva)

[`ux-py`](https://github.com/i2y/ux) (`ux bundle`) hace exactamente lo que el plan
pedía: `.app` con Python de `python-build-standalone`, cross-compile, codesign,
notarización, DMG. Es el camino mínimo de una sola herramienta.

**Riesgo**: es v0.1.6 (marzo 2026), 1 mantenedor, ~0 estrellas, sin actividad
reciente. Si se vuelve inmantenible, la alternativa es **BeeWare Briefcase**
(maduro, gran comunidad) — hay un bloque `[tool.briefcase]` listo en el
`pyproject.toml` como plan B.

`ux` se instala global, no como dependencia del proyecto: `uv tool install ux-py`.

### Bug real de Tcl/Tk arreglado: `TCL_LIBRARY`/`TK_LIBRARY` en `gui.py`

En sesión 2, tanto `uv run marimo-desktop` como el `.app` fallaban dentro del
entorno de Claude Code con `_tkinter.TclError: Can't find a usable
init.tcl`. En sesión 3 el usuario confirmó que `uv run marimo-desktop` SÍ
abría bien en su Terminal, así que quedó marcado como "artefacto del
sandbox". **Era una conclusión a medias**: en sesión 4 el usuario reportó que
haciendo doble clic en `dist/marimo-desktop.app` reproducía el mismo error
—la ventana nunca abría, caía al fallback `--headless` sin que se notara, y
además el icono del Dock quedaba "no responde" (forzar salida) porque ese
fallback no tiene ningún *run loop* que pueda recibir el Quit Apple Event de
macOS.

Causa raíz real: `uv`/`ux` crean el `.venv` con `bin/python` como symlink al
intérprete compartido en `~/.local/share/uv/python/cpython-*/`, pero
`_tkinter` busca `tcl*/tk*` relativos a `sys.prefix` (el `.venv`, donde esas
carpetas no existen) en vez de `sys.base_prefix` (donde sí están). El
Terminal del usuario probablemente ya tenía `TCL_LIBRARY`/`TK_LIBRARY`
puestos por su perfil de shell (típico con Homebrew) — Finder no hereda eso
al abrir un `.app` con doble clic, por eso solo fallaba ahí.

Arreglado en `gui.py` (`_fix_tcl_tk_library_paths()`, se ejecuta antes de
`import tkinter`): si `sys.prefix != sys.base_prefix`, busca `tcl*/init.tcl`
y `tk*/tk.tcl` bajo `sys.base_prefix/lib` y los pone en `TCL_LIBRARY`/
`TK_LIBRARY` si no estaban ya definidos. No depende de la versión exacta de
Tcl/Tk (glob + comprobación de fichero marcador, no "8.6" a fuego) ni de
tener un perfil de shell concreto. Verificado directamente contra el
intérprete empaquetado que fallaba (`tk.Tk()` pasó de excepción a `OK`).

## Caveats de ux-py 0.1.6

- **`--offline` genera un bundle roto**: el launcher busca un Python embebido que
  no está en el bundle. Por ahora → el primer arranque necesita red (descarga
  intérprete + wheels a `~/Library/Caches/ux/bundles/<hash>/`). Arranques
  siguientes: instantáneos.
- **`[tool.ux].include` debe listar `"src/"`** o el paquete no se empaqueta (ux no
  mapea el guion del nombre a `src/marimo_desktop/`).
- El bundle va **firmado ad-hoc** por ux. Localmente vale; una copia descargada
  necesita `--codesign` con Developer ID + `--notarize` para pasar Gatekeeper.
- `Info.plist` `CFBundleVersion` queda fijo en `1.0.0` (ux ignora `version`).
- El ejecutable corre desde el `.venv` de la caché, así que `sys.frozen` /
  `Contents/Resources` **no** sirven para detectar "estoy empaquetado".
  `paths.running_from_source()` lo resuelve mirando si hay un `pyproject.toml`
  escribible con nuestro nombre.

## Roadmap

- [x] Ventana Tk (start/stop, selector de carpeta + recientes, URL
      clicable + copiar)
- [x] Icono de la app (`assets/icon.png` → `.icns`) + nombre en el Dock
      (`CFBundleName` ya estaba bien) — solo visible en el `.app` empaquetado,
      no con `uv run` (ver nota de diseño abajo)
- [x] Bug de Tcl/Tk en el `.app` empaquetado arreglado (ver nota arriba)
- [ ] Asociación de archivos para `.py` de marimo
- [ ] `bundle_identifier` en minúsculas ya es correcto (reverse-DNS); revisar solo
  si cambia el usuario de GitHub
- [ ] CI (macOS / Windows / Linux) que produzca instaladores en cada tag

## Entorno / git

- Repo: **https://github.com/jfCoronel/marimo-desktop** (público, rama `main`).
- `user.email` puesto **solo en este repo** a `jfcoroneltoro@gmail.com`
  (el global del equipo original es `jfc@us.es` — no tocar el global).
- `gh` CLI instalado con Homebrew en el Mac de la sesión 1.
- Historial de chat y memoria de Claude Code son **locales** a cada máquina; este
  fichero es lo que viaja con el repo.

## Plan original (resumen) y alternativas descartadas

Plan: proyecto con `marimo` como dependencia → launcher Python que lanza `marimo
edit`/`run` y abre el navegador → `ux bundle --format app` → (opcional) ventana
nativa.

Descartadas:
- **PyInstaller + Tauri sidecar**: obliga a mantener una capa Rust/Tauri además
  del launcher.
- **pytauri** (Python vía PyO3 dentro de Tauri): más complejo, solo merece la pena
  si se necesita integración profunda con APIs nativas de Tauri.
- **uvbox**: no empaqueta Python (lo descarga en primer arranque), no hace `.app`
  ni firma, y es muy joven.
- **Positron / Pyzo**: IDEs con entorno propio, pero no ejecutan notebooks
  reactivos de marimo.
- **pywebview**: ver "Decisiones de arquitectura".
