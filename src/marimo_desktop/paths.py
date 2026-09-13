"""Filesystem locations: the notebooks folder, sample seeding, config dir."""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
from pathlib import Path


def _find_samples_dir() -> Path:
    """Locate the shipped sample notebooks.

    The packagers disagree about the layout: a dev checkout and an ux bundle
    put ``notebooks/`` two levels above this file, Briefcase puts it one level
    above (``Contents/Resources/app/notebooks``). Look for it rather than
    hard-coding one of them; falling back to the old guess keeps
    ``_seed_samples`` a no-op when there is nothing to seed.
    """
    here = Path(__file__).resolve()
    for parent in (here.parents[1], here.parents[2]):
        candidate = parent / "notebooks"
        if candidate.is_dir():
            return candidate
    return here.parents[2] / "notebooks"


SAMPLES_DIR = _find_samples_dir()


def running_from_source() -> bool:
    """True when run from a dev checkout (writable repo), not a packaged app.

    ux drops the bundle under ~/Library/Caches/ux/bundles/<hash>/, which is
    disposable — writing user notebooks there would lose them on the next
    version. So only treat the tree as user-writable if it's the real repo.
    """
    root = Path(__file__).resolve().parents[2]
    if "/Caches/" in str(root) or ".app/Contents/" in str(root):
        return False
    pyproject = root / "pyproject.toml"
    try:
        return (
            pyproject.is_file()
            and 'name = "marimo-desktop"' in pyproject.read_text(encoding="utf-8")
            and os.access(root, os.W_OK)
        )
    except OSError:
        return False


def default_notebooks_dir() -> Path:
    """The notebooks folder to use when the user hasn't picked one.

    Override with ``MARIMO_DESKTOP_NOTEBOOKS``.
    """
    env = os.environ.get("MARIMO_DESKTOP_NOTEBOOKS")
    if env:
        path = Path(env).expanduser()
    elif running_from_source():
        path = SAMPLES_DIR
    else:
        path = Path.home() / "marimo notebooks"
    return ensure_notebooks_dir(path)


def ensure_notebooks_dir(path: Path) -> Path:
    path = path.expanduser()
    path.mkdir(parents=True, exist_ok=True)
    _seed_samples(path)
    return path


def _seed_samples(target: Path) -> None:
    """Copy shipped sample notebooks into an empty user notebooks folder."""
    if target == SAMPLES_DIR or not SAMPLES_DIR.is_dir():
        return
    if any(target.glob("*.py")):
        return
    for sample in SAMPLES_DIR.glob("*.py"):
        with contextlib.suppress(OSError):
            shutil.copy2(sample, target / sample.name)


def config_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / "marimo-desktop"
    path.mkdir(parents=True, exist_ok=True)
    return path
