# marimo-desktop

[![CI](https://github.com/jfCoronel/marimo-desktop/actions/workflows/ci.yml/badge.svg)](https://github.com/jfCoronel/marimo-desktop/actions/workflows/ci.yml)

A self-contained desktop app for [marimo](https://github.com/marimo-team/marimo):
it ships its own Python interpreter and marimo install, so there is nothing to
`pip install` and no venv to manage. Double-click → marimo opens.

Status: **v1, verified on macOS, Linux and Windows** — a small Tk control
window (`Start/Stop`, folder picker + recent folders, clickable URL + copy
button) plus a `--headless` mode. Every push builds the bundle on all three
platforms and launches it to check marimo actually comes up. No `pywebview` —
the launcher is a native control panel and marimo itself opens in a real
browser.

Downloads for all three platforms are on the
[releases page](https://github.com/jfCoronel/marimo-desktop/releases). They
are **unsigned** — no Apple Developer account, no Windows certificate — so
macOS and Windows will both warn you; the release notes spell out the
standard steps to open them anyway.

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

Tests and lint (`pytest` + `ruff`, in the `dev` dependency group):

```sh
uv sync --group dev
uv run pytest          # ~60 tests, no marimo server is started
uv run ruff check .
uv run ruff format .
```

The suite covers everything except the Tk widgets themselves: server command
construction and teardown, notebook-folder resolution and sample seeding, the
prefs file, argv handling (including the `-psn_`/`-NS` noise macOS hands a
bundled app), the Tcl/Tk library-path fix, and pyproject invariants that have
already drifted once (version in three places, `include = ["src/"]`). Nothing
touches the real `~/marimo notebooks` or the user config — `conftest.py`
redirects both.

[CI](.github/workflows/ci.yml) runs the same three commands on macOS, Linux and
Windows × Python 3.12/3.13, plus a wheel/sdist build and a per-platform bundle
build that is launched for real (see `scripts/smoke_bundle.py` below).

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
ux bundle --output ./dist/                         # plain binary (Linux/Windows; `--format app` is macOS-only)
ux bundle --target linux-x86_64 --output ./dist/   # cross-compile a Linux binary
```

Then `open dist/marimo-desktop.app`.

Verify a build actually runs (launches it, waits for the marimo server to
answer, shuts it down) — works on any of the three platforms:

```sh
python scripts/smoke_bundle.py dist/marimo-desktop.app     # macOS
python scripts/smoke_bundle.py dist/marimo-desktop         # Linux
python scripts/smoke_bundle.py dist/marimo-desktop.exe     # Windows
```

CI runs exactly that on macOS, Linux and Windows and keeps the bundles as
downloadable artifacts for 14 days.

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

## Release

Tag and push; [`release.yml`](.github/workflows/release.yml) does the rest —
builds on each platform's own runner, launches every artifact to check it
serves marimo, then publishes a GitHub release.

```sh
# bump version in pyproject.toml and src/marimo_desktop/__init__.py first
git tag v0.3.0 && git push origin v0.3.0
```

The version in the tag must match `pyproject.toml` — the workflow refuses the
build otherwise. A release can be rebuilt from the Actions tab
("Run workflow" → existing tag) without re-tagging.

What each platform gets:

| Platform | Artifact | Built with |
|---|---|---|
| macOS (arm64 + Intel) | `.dmg`, drag to Applications | `ux bundle --format app --dmg` |
| Windows x64 | per-user installer `.exe` | [Inno Setup](packaging/windows/installer.iss) |
| Linux x86_64 | `.tar.gz` + `install.sh` | [`scripts/package_linux.py`](scripts/package_linux.py) |

`--format app` is macOS-only, so on Linux and Windows ux emits a bare
executable and the desktop integration (icon, menu entry, uninstaller) is
added by the packaging step. Signing is skipped: `ux --codesign` needs an
Apple Developer ID, and `--dmg` works fine without it — the bundle stays
ad-hoc signed. Install instructions for unsigned builds live in
[`scripts/release_notes.py`](scripts/release_notes.py), which generates the
release body.

## Roadmap

- [x] Tk control window (Start/Stop, folder picker + recent folders,
      clickable URL + copy button)
- [x] App icon + Dock name polish (`assets/icon.png` → `.icns`)
- [x] Test suite + ruff, run on CI across macOS / Linux / Windows
- [x] Linux and Windows bundles built and launched in CI (macOS `.app` ~18 MB,
      Linux binary 24 MB, Windows `.exe` 22 MB)
- [x] Icon / desktop integration for Linux (.desktop + installer) and Windows
      (Inno Setup installer)
- [x] Tagged releases publishing installers for all three platforms
- [ ] Signing + notarisation (needs a paid Apple Developer account; until then
      downloads need the manual "open anyway" step)
- ~~File association for `.py`~~ — dropped: a marimo notebook is an ordinary
  `.py`, so there is no extension to claim without fighting every editor on
  the machine, and `marimo edit` simply exits on a non-notebook `.py` with no
  console to show the error in. See NOTES.md.
