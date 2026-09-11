# marimo-desktop

A self-contained desktop app for [marimo](https://github.com/marimo-team/marimo):
it ships its own Python interpreter and marimo install, so there is nothing to
`pip install` and no venv to manage. Double-click → marimo opens.

Status: **v1, verified** — a small Tk control window (`Start/Stop`, folder
picker + recent folders, clickable URL + copy button) plus a `--headless`
mode. Both `uv run marimo-desktop` and the packaged `dist/marimo-desktop.app`
work. No `pywebview` — the launcher is a native control panel and marimo
itself opens in a real browser.

Design decisions, packaging caveats and the roadmap are in [`NOTES.md`](NOTES.md).

## How it works

Default (`marimo-desktop`, no args) opens the Tk window (`gui.py`). It:

1. lets you pick the notebooks folder (remembered in `config.json`), or jump
   back to one of the last 8 via **Recent ▾**
2. **Start marimo** → `server.py` starts `python -m marimo edit <folder>
   --headless --no-token` on a free `127.0.0.1` port (bundled interpreter)
3. polls until the server answers, then shows the URL as a clickable link
   (opens it in the system's default browser) plus a **Copy URL** button —
   nothing opens automatically, so pasting the URL into a different browser is
   just as easy as clicking the link
4. **Stop** / closing the window terminates the server

A small footer shows the Python/`uv`/marimo versions actually in use (read
from `pyvenv.cfg` and package metadata — no subprocess calls) plus a
copyright line.

Creating/opening individual notebooks is deliberately left to marimo itself:
pointing `marimo edit` at a folder (step 2 above) already gives you its own
directory home page in the browser — new notebook, open, recents — so the Tk
window doesn't duplicate that; see NOTES.md.

`marimo-desktop --headless [notebook]` skips the window: start, open browser,
block until Ctrl-C — for scripts and automation. `--run` uses app mode
(`marimo run`); `--no-browser` suppresses the browser (headless only).

Notebooks folder:

- dev checkout: `./notebooks`
- packaged app: `~/marimo notebooks` (created + seeded with samples on first run)
- override: `MARIMO_DESKTOP_NOTEBOOKS=/some/path`, or pick one in the window

Modules: `gui.py` (window) · `server.py` (`MarimoServer`) · `browsers.py` (open
the default browser) · `config.py` (JSON prefs) · `paths.py` (folder
resolution) · `launcher.py` (entry point / headless).

## Develop

```sh
uv sync
uv run marimo-desktop                       # the control window
uv run marimo-desktop --headless            # no window: start + open browser
uv run marimo-desktop --headless notebooks/welcome.py
uv run marimo-desktop --headless --run notebooks/welcome.py   # app mode
```

## Package (ux-py)

Packaging uses [`ux-py`](https://github.com/i2y/ux), configured in `pyproject.toml`
under `[tool.ux]`. The app icon (`assets/icon.png`, original artwork, not
marimo's own logo) is converted to `.icns` automatically on build; the Dock
name comes from `bundle_name`. Install it once, globally:

```sh
uv tool install ux-py
```

Build:

```sh
ux bundle --format app --output ./dist/            # -> dist/marimo-desktop.app  (verified working)
ux bundle --format app --codesign --dmg --output ./dist/    # ad-hoc signed .dmg
ux bundle --format app --codesign --notarize --dmg --output ./dist/   # Developer ID + Apple notary
ux bundle --target linux-x86_64 --output ./dist/   # cross-compile a Linux binary
```

Then `open dist/marimo-desktop.app`.

### Known behaviour / caveats (ux-py 0.1.6 — pre-1.0, one maintainer)

- **First run bootstraps online**: the `.app` is ~21 MB and downloads a
  python-build-standalone interpreter + wheels on first launch into
  `~/Library/Caches/ux/bundles/<hash>/`. Subsequent launches are instant. Wipe
  that dir to force a clean re-bootstrap.
- **`--offline` is broken**: it builds a bundle whose launcher looks for a
  bundled Python that isn't there. Don't use it until upstream fixes it — which
  means "needs network once" for now, not truly offline.
- **`[tool.ux].include` must list `src/`** — ux doesn't map the hyphenated
  project name to `src/marimo_desktop/`, so without it the package isn't shipped.
- The bundle is **ad-hoc signed** by ux (`codesign` identifier `ux-…`). Fine
  locally; a downloaded copy still needs `--codesign` with a Developer ID +
  `--notarize` to pass Gatekeeper cleanly.
- `Info.plist` `CFBundleVersion` is hard-coded `1.0.0` (ux ignores `version`).

If ux-py stays too flaky, the fallback is BeeWare Briefcase (mature, bigger
community); a `[tool.briefcase]` block is kept in `pyproject.toml` for that.

## Roadmap

- [x] Tk control window (Start/Stop, folder picker + recent folders,
      clickable URL + copy button)
- [x] App icon + Dock name polish (`assets/icon.png` → `.icns`)
- [ ] File association for `.py` marimo notebooks
- [ ] CI matrix (macOS / Windows / Linux) producing installers on tag
