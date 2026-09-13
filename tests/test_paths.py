"""Notebook folder resolution, sample seeding, config dir."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from marimo_desktop import paths


def test_env_var_wins_over_everything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "elsewhere"
    monkeypatch.setenv("MARIMO_DESKTOP_NOTEBOOKS", str(target))

    resolved = paths.default_notebooks_dir()

    assert resolved == target
    assert resolved.is_dir(), "the folder should be created, not just named"


def test_env_var_expands_a_tilde(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # expanduser() reads HOME on POSIX and USERPROFILE on Windows.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("MARIMO_DESKTOP_NOTEBOOKS", "~/nb")

    assert paths.default_notebooks_dir() == tmp_path / "nb"


def test_running_from_source_is_true_in_this_checkout() -> None:
    """The suite runs against the repo, so the dev-checkout branch must hold."""
    assert paths.running_from_source() is True


def test_ensure_notebooks_dir_seeds_the_samples(tmp_path: Path) -> None:
    target = tmp_path / "fresh"

    paths.ensure_notebooks_dir(target)

    shipped = {p.name for p in paths.SAMPLES_DIR.glob("*.py")}
    assert shipped, "the repo should ship at least one sample notebook"
    assert shipped <= {p.name for p in target.glob("*.py")}


def test_seeding_never_overwrites_an_existing_notebook(tmp_path: Path) -> None:
    target = tmp_path / "mine"
    target.mkdir()
    mine = target / "welcome.py"
    mine.write_text("# my own work", encoding="utf-8")

    paths.ensure_notebooks_dir(target)

    assert mine.read_text(encoding="utf-8") == "# my own work"


def test_seeding_skips_the_samples_dir_itself() -> None:
    """Dev checkout: the notebooks folder *is* the samples folder — no self-copy."""
    before = sorted(p.name for p in paths.SAMPLES_DIR.glob("*.py"))

    paths.ensure_notebooks_dir(paths.SAMPLES_DIR)

    assert sorted(p.name for p in paths.SAMPLES_DIR.glob("*.py")) == before


def test_config_dir_is_platform_appropriate_and_exists() -> None:
    path = paths.config_dir()

    assert path.is_dir()
    assert path.name == "marimo-desktop"
    if sys.platform == "darwin":
        assert "Library/Application Support" in str(path)
    elif sys.platform == "win32":
        assert "AppData" in str(path) or "APPDATA" in str(path)


def test_config_dir_follows_xdg_on_linux(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if sys.platform != "linux":
        pytest.skip("XDG layout only applies on Linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert paths.config_dir() == tmp_path / "marimo-desktop"
