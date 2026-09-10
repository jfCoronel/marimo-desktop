# NOTES — contexto del proyecto

Notas de diseño y decisiones que no se deducen del código. El *cómo* está en
[`README.md`](README.md); esto es el *por qué* y el estado.

Última actualización: 2026-09-10 (fin de la sesión 1).

---

## Objetivo

Un equivalente a `jupyter-desktop` **para [marimo](https://github.com/marimo-team/marimo)**:
una app de escritorio que trae su propio Python + marimo, de forma que el usuario
final no instala nada (ni Python, ni `uv`, ni un venv).

No existe nada equivalente: la org `marimo-team` no tiene `marimo-desktop`; hay
`marimo-jupyter-extension` y `jetbrains-marimo` (PoC), pero ninguna app standalone
con Python embebido. Lo más cercano hoy es `uvx marimo edit`, que aún exige `uv`.

## Estado actual (v1, verificado)

- **Ventana de control Tk** (`gui.py`): selector de carpeta, botón Arrancar/Parar,
  selector de navegador (detecta los instalados, recuerda la elección en
  `config.json`), URL clicable, copiar URL. Cerrar la ventana para el servidor.
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

### ux-py como empaquetador (con Briefcase de reserva)

[`ux-py`](https://github.com/i2y/ux) (`ux bundle`) hace exactamente lo que el plan
pedía: `.app` con Python de `python-build-standalone`, cross-compile, codesign,
notarización, DMG. Es el camino mínimo de una sola herramienta.

**Riesgo**: es v0.1.6 (marzo 2026), 1 mantenedor, ~0 estrellas, sin actividad
reciente. Si se vuelve inmantenible, la alternativa es **BeeWare Briefcase**
(maduro, gran comunidad) — hay un bloque `[tool.briefcase]` listo en el
`pyproject.toml` como plan B.

`ux` se instala global, no como dependencia del proyecto: `uv tool install ux-py`.

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

- [x] Ventana Tk (arrancar/parar, selector de carpeta, selector de navegador)
- [ ] **Fase 2**: en la misma ventana —
  - `Nuevo notebook…`: nombre + carpeta → escribe stub marimo → abre
  - `Abrir notebook…`: file picker → `marimo edit <fichero>`
  - lista de recientes
- [ ] Icono de la app + nombre en el Dock
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
