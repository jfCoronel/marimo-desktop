"""Guards on pyproject.toml itself.

These catch the two ways this project has already drifted: a version bumped
in one place but not the other, and packaging metadata that silently ships a
broken bundle (see the ux-py caveats in NOTES.md).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import marimo_desktop

PYPROJECT = tomllib.loads(
    (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
)


def test_dunder_version_matches_pyproject() -> None:
    assert marimo_desktop.__version__ == PYPROJECT["project"]["version"]


def test_briefcase_version_matches_pyproject() -> None:
    """The fallback packager keeps its own copy of the version — keep them equal."""
    assert PYPROJECT["tool"]["briefcase"]["version"] == PYPROJECT["project"]["version"]


def test_ux_ships_the_source_package() -> None:
    """ux 0.1.6 doesn't map `marimo-desktop` to src/marimo_desktop/; without an
    explicit "src/" in include, the bundle is built without the app in it."""
    assert "src/" in PYPROJECT["tool"]["ux"]["include"]


def test_ux_ships_the_sample_notebooks() -> None:
    assert "notebooks/" in PYPROJECT["tool"]["ux"]["include"]


def test_ux_entry_point_exists() -> None:
    entry = PYPROJECT["tool"]["ux"]["entry"]
    assert entry in PYPROJECT["project"]["scripts"]


def test_bundle_identifier_is_reverse_dns_lowercase() -> None:
    identifier = PYPROJECT["tool"]["ux"]["macos"]["bundle_identifier"]
    assert identifier == identifier.lower()
    assert identifier.count(".") >= 2


def test_declared_icon_exists() -> None:
    icon = PYPROJECT["tool"]["ux"]["macos"]["icon"]
    assert (Path(__file__).resolve().parents[1] / icon).is_file()


def test_packaging_tools_are_not_runtime_dependencies() -> None:
    """ux/briefcase must stay out of [project.dependencies] — they'd be bundled."""
    deps = " ".join(PYPROJECT["project"]["dependencies"]).lower()
    assert "ux" not in deps.split()
    assert "briefcase" not in deps


def test_pinned_marimo_matches_the_lock() -> None:
    """The Briefcase app ships no marimo and installs server.MARIMO_VERSION;
    the ux builds install the locked one. Both must be the same marimo."""
    from marimo_desktop.server import MARIMO_VERSION

    lock = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "uv.lock").read_text(encoding="utf-8")
    )
    [locked] = [pkg["version"] for pkg in lock["package"] if pkg["name"] == "marimo"]
    assert locked == MARIMO_VERSION


def test_briefcase_does_not_bundle_marimo() -> None:
    """Everything runs on the Python uv provides; a bundled marimo is dead weight."""
    requires = PYPROJECT["tool"]["briefcase"]["app"]["marimo-desktop"]["requires"]
    assert not any(req.lower().startswith("marimo") for req in requires)


def test_briefcase_requires_override_replaces_the_whole_list() -> None:
    """The workflows pass this with -C; it must parse and leave marimo out."""
    import importlib.util

    script = Path(__file__).resolve().parents[1] / "scripts" / "briefcase_requires.py"
    spec = importlib.util.spec_from_file_location("briefcase_requires", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    parsed = tomllib.loads(module.override())
    assert parsed["requires"] == PYPROJECT["tool"]["briefcase"]["app"]["marimo-desktop"]["requires"]
    assert "psutil>=5.9" in parsed["requires"]
    assert not any(req.startswith("marimo") for req in parsed["requires"])
