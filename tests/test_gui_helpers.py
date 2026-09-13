"""Pure helpers from gui.py — no Tk window is created here.

Importing the module is safe headless (it only imports tkinter); building an
App() is not, so nothing below does.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from marimo_desktop import config, gui

# -- recent folders -------------------------------------------------------


def test_add_recent_puts_the_newest_first(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"

    gui._add_recent(first)
    gui._add_recent(second)

    assert config.get("recent_folders") == [str(second), str(first)]


def test_add_recent_deduplicates_instead_of_growing(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"

    gui._add_recent(first)
    gui._add_recent(second)
    gui._add_recent(first)

    assert config.get("recent_folders") == [str(first), str(second)]


def test_add_recent_is_capped(tmp_path: Path) -> None:
    folders = [tmp_path / f"f{i}" for i in range(gui._MAX_RECENTS + 5)]

    for folder in folders:
        gui._add_recent(folder)

    recents = config.get("recent_folders")
    assert len(recents) == gui._MAX_RECENTS
    assert recents[0] == str(folders[-1])


# -- path display ---------------------------------------------------------


def test_shorten_leaves_short_paths_alone() -> None:
    """Short enough to show whole: printed verbatim, native separators and all."""
    path = Path("/a/b")
    assert gui._shorten(path) == str(path)


def test_shorten_elides_the_middle_of_a_deep_path() -> None:
    assert gui._shorten(Path("/Users/x/Documents/work/nb")) == ".../Documents/work/nb"


# -- Tcl/Tk library discovery --------------------------------------------


def test_find_lib_dir_prefers_the_highest_version(tmp_path: Path) -> None:
    for name in ("tcl8.6", "tcl9.0"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "init.tcl").touch()

    assert gui._find_lib_dir(tmp_path, "tcl", "init.tcl") == tmp_path / "tcl9.0"


def test_find_lib_dir_ignores_a_dir_without_the_marker(tmp_path: Path) -> None:
    (tmp_path / "tcl9.0").mkdir()  # no init.tcl inside

    assert gui._find_lib_dir(tmp_path, "tcl", "init.tcl") is None


def test_find_lib_dir_returns_none_when_nothing_matches(tmp_path: Path) -> None:
    assert gui._find_lib_dir(tmp_path, "tk", "tk.tcl") is None


def test_tcl_fix_is_a_no_op_outside_a_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "prefix", "/usr")
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    monkeypatch.delenv("TCL_LIBRARY", raising=False)

    gui._fix_tcl_tk_library_paths()

    assert "TCL_LIBRARY" not in __import__("os").environ


def test_tcl_fix_points_at_the_base_prefix_libraries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The packaged-app bug: tkinter looks under sys.prefix, the files are under
    sys.base_prefix. Regression test for the Finder double-click crash."""
    base_lib = tmp_path / "base" / "lib"
    (base_lib / "tcl9.0").mkdir(parents=True)
    (base_lib / "tcl9.0" / "init.tcl").touch()
    (base_lib / "tk9.0").mkdir()
    (base_lib / "tk9.0" / "tk.tcl").touch()

    monkeypatch.setattr(sys, "prefix", str(tmp_path / "venv"))
    monkeypatch.setattr(sys, "base_prefix", str(tmp_path / "base"))
    monkeypatch.delenv("TCL_LIBRARY", raising=False)
    monkeypatch.delenv("TK_LIBRARY", raising=False)

    gui._fix_tcl_tk_library_paths()

    import os

    assert os.environ["TCL_LIBRARY"] == str(base_lib / "tcl9.0")
    assert os.environ["TK_LIBRARY"] == str(base_lib / "tk9.0")


def test_tcl_fix_respects_an_existing_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A user whose shell already sets these (Homebrew Tk) keeps their choice."""
    base_lib = tmp_path / "base" / "lib"
    (base_lib / "tcl9.0").mkdir(parents=True)
    (base_lib / "tcl9.0" / "init.tcl").touch()

    monkeypatch.setattr(sys, "prefix", str(tmp_path / "venv"))
    monkeypatch.setattr(sys, "base_prefix", str(tmp_path / "base"))
    monkeypatch.setenv("TCL_LIBRARY", "/opt/homebrew/lib/tcl8.6")

    gui._fix_tcl_tk_library_paths()

    import os

    assert os.environ["TCL_LIBRARY"] == "/opt/homebrew/lib/tcl8.6"


# -- footer ---------------------------------------------------------------


def test_uv_version_reads_pyvenv_cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Read from pyvenv.cfg rather than shelling out — `uv` isn't on PATH in the app."""
    (tmp_path / "pyvenv.cfg").write_text(
        "home = /somewhere\nuv = 0.12.13\nversion_info = 3.12.7\n", encoding="utf-8"
    )
    monkeypatch.setattr(sys, "prefix", str(tmp_path))

    assert gui._uv_version() == "0.12.13"


def test_uv_version_is_unknown_without_a_pyvenv_cfg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "prefix", str(tmp_path))

    assert gui._uv_version() == "?"


def test_footer_reports_versions_and_copyright() -> None:
    text = gui._footer_text()

    assert "Python" in text
    assert "marimo" in text
    assert f"© {gui._COPYRIGHT_YEAR}" in text
