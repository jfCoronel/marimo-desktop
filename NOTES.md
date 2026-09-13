# NOTES — contexto del proyecto

Notas de diseño y decisiones que no se deducen del código. El *cómo* está en
[`README.md`](README.md); esto es el *por qué* y el estado.

Última actualización: 2026-09-13 (sesión 5).

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

### Tests, lint y CI (sesión 5)

Hasta aquí el proyecto no tenía ni una sola prueba ni configuración de lint,
pese a que el código ya llevaba `# noqa: E402/BLE001/S603/S310/A001/FBT003`
—códigos de ruff que no validaba nadie. Se añadió:

- **`tests/`** (~60 pruebas, `pytest`). Cubren todo menos los widgets Tk:
  construcción del comando de marimo y parada del subproceso, resolución de
  la carpeta de notebooks + sembrado de ejemplos, el fichero de prefs, el
  manejo de `argv`, el arreglo de `TCL_LIBRARY`/`TK_LIBRARY` y una serie de
  invariantes del propio `pyproject.toml`.
  - **Nada de servidor marimo real** en la suite: sería lenta y dependiente de
    red/puertos. Las tres cosas que sí necesitan un proceso de verdad
    (`stop()` mata al hijo) usan un `python -c "time.sleep(30)"` como cebo.
  - `conftest.py` redirige `config._PATH` y borra `MARIMO_DESKTOP_NOTEBOOKS`
    en **todas** las pruebas: la suite nunca debe escribir en el config real
    ni en `~/marimo notebooks`.
  - `tests/test_packaging.py` guarda las dos formas en que este repo ya se
    había desincronizado: la versión (estaba `0.1.0` en `__init__.py` y
    `0.2.0` en `pyproject.toml` — arreglado) y los metadatos de empaquetado
    que producen un bundle silenciosamente roto (`include` sin `"src/"`).

- **ruff** (`[tool.ruff]` en `pyproject.toml`), `line-length = 100`, con `BLE`
  y `FBT` en el `select` precisamente para que los `noqa` que ya había
  signifiquen algo. `notebooks/` queda **excluido**: una celda de marimo acaba
  en una expresión suelta a propósito (es su salida) y `B018` la marca siempre
  — no es estilo nuestro que corregir. También se adoptó `ruff format` (el
  diff sobre el código existente era de 3 ficheros, trivial).

- **`.github/workflows/ci.yml`**: matriz macOS/Linux/Windows × Python
  3.12/3.13 con lint + format + tests, más un job que construye wheel y sdist.
  Es la **primera vez que Linux y Windows tocan este código**; ojo, solo se
  ejercita la parte Python (las ramas por plataforma de `paths.py`), no los
  bundles — construirlos y ejecutarlos de verdad sigue pendiente.
  Hay un paso suelto `import tkinter` antes de `pytest` para que, si un runner
  no trae Tk, el fallo se lea como lo que es y no como un error opaco de
  recolección.

**Bug real encontrado por las pruebas** (`launcher.main`): el filtro de
argumentos que macOS le pasa a una app empaquetada quitaba los *flags*
`-NS…`/`-AppleLanguages` pero **no su valor**, así que `(en)` sobrevivía y
argparse lo tomaba como el notebook posicional → la app arrancaba en modo
headless con una ruta fantasma en vez de abrir la ventana. Sustituido por
`_strip_macos_args()`, que descarta el flag y su valor (y no se come el
siguiente argumento si este empieza por `-`, es decir, si es otro flag).

De paso, `_add_recent` pasó de método de `App` a función de módulo: no usaba
`self` para nada y así se puede probar sin abrir una ventana.

**Lo que dijo el primer CI** (dos fallos, ambos instructivos):

- *Windows*: cuatro pruebas comparaban contra rutas POSIX literales (`"/a"`),
  pero allí `str(Path("/a"))` es `"\a"`. Fallo de las pruebas, no del código;
  ahora construyen las rutas con `tmp_path` y comparan contra `str()` de lo
  mismo.
- *Linux*: `uv` cogió el Python **del sistema** (`/usr/bin/python3.12`), que en
  Ubuntu viene sin `tkinter` → el chequeo de Tk falló. No decía nada sobre
  nuestro intérprete. Arreglado con `UV_PYTHON_PREFERENCE: only-managed` en el
  workflow, que fija un python-build-standalone en los tres runners —
  exactamente el tipo de intérprete que ux embebe en el bundle.

Con eso, **7/7 jobs en verde**, y de paso un dato que no teníamos: el
intérprete gestionado trae Tk en las tres plataformas — **Linux Tk 9.0,
Windows Tk 8.6, macOS Tk 8.6** (CPython 3.12.14). Es decir, la ventana de
control no es un problema fuera de macOS; lo que sigue sin probarse es el
empaquetado en sí (`ux bundle --target …`), no la GUI.

### Linux y Windows: el bundle funciona (sesión 5)

Hasta aquí solo estaba verificado el `.app` de macOS, y solo a mano (doble
clic del autor). Ahora el CI **construye el bundle en las tres plataformas y
lo ejecuta de verdad** (`scripts/smoke_bundle.py`: lanza el artefacto en
`--headless`, espera la línea de "listo", comprueba por HTTP que el servidor
responde y lo mata). Resultado del primer intento completo:

| Plataforma | Artefacto | Tamaño | Smoke |
|---|---|---|---|
| macOS | `marimo-desktop.app` (`--format app`) | ~18 MB | ✅ |
| Linux | `marimo-desktop` (binario) | 24,1 MB | ✅ |
| Windows | `marimo-desktop.exe` (binario) | 22,3 MB | ✅ |

`--format app` es **solo macOS**; en Linux y Windows ux produce un binario
suelto (sin icono ni nombre de Dock, claro). Los tres bootstrapean su
intérprete en el primer arranque, igual que el `.app`.

Dos fallos del primer intento, **ambos del arnés de prueba, no de la app**
(Windows llegó a imprimir "the bundled marimo server answered" antes de
fallar):

- Matar solo al proceso lanzador dejaba **vivo el servidor marimo** que este
  había arrancado. Ese huérfano mantenía abierto el fichero de log → en
  Windows la limpieza del temporal revienta con `WinError 32`; y mantenía
  bloqueado el caché de uv del runner → el job de macOS se quedaba 300 s
  esperando el lock en `Post Install uv`. Comprobado en local: tras dos
  pruebas previas quedaban dos `marimo edit` vivos.
- Arreglado con `terminate_tree()` (grupo de procesos en POSIX,
  `taskkill /T /F` en Windows) + `ignore_cleanup_errors=True` en el
  temporal. El job de bundle además ya no usa el caché de uv, que no
  necesitaba.

Lo que sigue **sin** resolver para distribuir fuera de tu máquina: firma y
notarización (macOS pedirá permiso o dirá "app dañada"), y que los binarios
de Linux/Windows no tienen icono ni integración de escritorio.

### Instaladores y release (sesión 5)

Decisión del usuario: **no se paga la cuenta de Apple** (99 $/año), así que
las descargas van sin firmar y quien las instale tiene que forzar la
apertura. Consecuencias comprobadas, no supuestas:

- `ux bundle --codesign` **falla** sin Developer ID (*"No code signing
  identities found"*), pero **`--dmg` solo, sin `--codesign`, sí funciona** →
  ese es el camino. El `.app` queda con firma ad-hoc (la que ux pone siempre).
- `spctl -a -vvv -t exec dist/marimo-desktop.app` → rechazado. Y en macOS 15+
  (aquí 26.6.2) Apple **eliminó el atajo de clic derecho → Abrir** para apps
  no notarizadas.

**Corregido tras probar la release real (el usuario instaló el `.dmg`
publicado)**: el mensaje que sale **no** es "no se ha podido verificar" sino
**"está dañado"**, y esa variante **no ofrece ninguna salida por interfaz** —
no aparece nada en Privacidad y seguridad. Las notas de la 0.3.0 decían
"Abrir igualmente" y mandaban al usuario a buscar un botón inexistente;
reescritas.

Causa: la firma que deja ux es **inválida**, no solo "sin notarizar":

```
codesign --verify dist/marimo-desktop.app
  → code has no resources but signature indicates they must be present
codesign -dvvv → flags=0x20002(adhoc,linker-signed), Sealed Resources=none
```

Y **no se puede re-firmar**: `codesign --force --deep --sign -` falla con
`main executable failed strict validation`, igual que firmando solo el
binario interno. Motivo: ux construye un ejecutable autoextraíble
**añadiendo el payload al final del Mach-O**, lo que rompe la estructura que
`codesign` exige. No es un flag mal puesto: con ux 0.1.6 (y es la última
versión en PyPI, comprobado) **no hay firma válida posible** para el `.app`.

Único remedio actual para el usuario: `xattr -dr com.apple.quarantine
/Applications/marimo-desktop.app`. Para quitar ese paso hace falta o bien la
cuenta de Apple (que no arregla esto por sí sola: una firma inválida sigue
siendo inválida), o bien **cambiar de empaquetador en macOS** — es
exactamente el escenario para el que `[tool.briefcase]` lleva ahí desde el
principio. Briefcase genera un `.app` con estructura estándar, firmable
ad-hoc de verdad (`--adhoc-sign`), lo que degradaría el problema a la ruta
normal de "app sin verificar" con su botón de *Abrir igualmente*.

Empaquetado por plataforma (`--format app` es solo macOS, así que Linux y
Windows reciben un binario pelado y hay que vestirlo):

- **Linux**: `scripts/package_linux.py` arma un `.tar.gz` con el binario, el
  icono, un `.desktop` y un `install.sh` per-user (todo bajo `~/.local`, sin
  root). El `Exec=` del `.desktop` va con marcador `__EXEC__` que el
  instalador sustituye por la ruta absoluta: un lanzador del menú **no tiene
  por qué llevar `~/.local/bin` en el `PATH`**.
- **Windows**: instalador de **Inno Setup**
  (`packaging/windows/installer.iss`), `PrivilegesRequired=lowest` para que no
  pida administrador. `ArchitecturesAllowed=x64` en vez de `x64compatible`
  porque este último exige Inno 6.3+ y no controlamos la versión del runner.
  El `.exe` que produce ux lleva el icono genérico de ux; los accesos directos
  apuntan al nuestro vía `IconFilename` (`assets/icon.ico`, generado con
  Pillow desde el PNG igual que el `.icns`).
- **macOS**: `.dmg` de ux, con el `.app` y el enlace a `/Applications`
  dentro (verificado montándolo). **Solo Apple Silicon**: los runners
  `macos-13` (Intel) se quedan encolados indefinidamente (25+ min y
  cancelado), y compilar cruzado **no vale** — `ux bundle --format app
  --target darwin-x86_64` produce un `.app` cuyo ejecutable sigue siendo
  **arm64** (`file …/Contents/MacOS/marimo-desktop` → `Mach-O 64-bit
  executable arm64`), o sea un DMG "de Intel" que no arranca en un Intel.
  Curiosamente `ux bundle --target darwin-x86_64` **sin** `--format app` sí
  da un binario x86_64 de verdad (verificado arrancándolo bajo Rosetta), así
  que el fallo está en el camino del bundle `.app`. Otro caveat de ux 0.1.6.

El workflow `release.yml` se dispara con tags `v*`, **rechaza el build si el
tag no coincide con la versión de `pyproject.toml`**, construye en el runner
nativo de cada plataforma (incluido `macos-13` para Intel), pasa el smoke
test a cada artefacto y publica la release. Se puede relanzar desde la
pestaña Actions con un tag existente sin volver a etiquetar.

La versión ahora se ve en la app: título de la ventana y primera línea del
pie (`marimo desktop 0.3.0 · © 2026 jfCoronel`), leída de `__version__` —
necesario para saber qué build tienes cuando la descargas.

### Asociación de archivos `.py`: descartada (sesión 5)

Estaba en el roadmap desde el principio; al ir a implementarla, el usuario
preguntó qué pasaría exactamente al hacer doble clic, y la respuesta la
mata. Comprobado ejecutando `marimo edit` sobre un `.py` normal:

```
Error: Python script not recognized as a marimo notebook.
  Tip: Try converting with
    marimo convert plain.py -o plain_nb.py
```

El fichero **no se modifica** (no hay riesgo de destrozar el script de
nadie), pero **el servidor sale inmediatamente**. Lanzado desde Finder no
hay terminal donde leer ese error: el usuario vería el icono rebotar en el
Dock y nada más. Habría que construir diálogos de error nativos solo para
ese caso.

Y el problema de fondo es peor: **un notebook de marimo es un `.py`
indistinguible de cualquier otro**. No hay extensión propia que reclamar, así
que asociar `.py` significa competir con VS Code/PyCharm por *todos* los
ficheros Python del sistema; con `LSHandlerRank = Alternate` lo único que se
gana es una entrada más en "Abrir con".

Coste que se habría pagado por eso: script de post-proceso del `Info.plist`
en cada build (ux 0.1.6 no expone `CFBundleDocumentTypes`; el plist generado
tiene 6 claves) + handler de Apple Events
(`root.createcommand("::tk::mac::OpenDocument", …)`, porque en macOS el doble
clic sobre un documento **no llega por `argv`**) + los diálogos de error de
arriba. Todo ello para duplicar algo que marimo ya hace: su página de inicio
lista y abre los notebooks de la carpeta.

Lo que sí queda cubierto sin nada de esto: `marimo-desktop notebook.py` desde
la línea de comandos ya abre un fichero concreto.

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
- [x] Suite de tests + ruff + CI (macOS / Linux / Windows × Python 3.12/3.13)
- ~~Asociación de archivos para `.py` de marimo~~ — **descartado** en sesión 5,
  ver la nota de diseño más abajo.
- [ ] `bundle_identifier` en minúsculas ya es correcto (reverse-DNS); revisar solo
  si cambia el usuario de GitHub
- [x] Workflow de release: instaladores para las tres plataformas publicados
  en cada tag (sin firmar, por decisión de coste)
- [ ] Firma + notarización, si algún día se paga la cuenta de Apple
- [x] Construir y ejecutar de verdad los bundles de Linux y Windows (CI, con
  smoke test del artefacto en las tres plataformas)

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
