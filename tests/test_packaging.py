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
