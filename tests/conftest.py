"""Shared fixtures.

Everything that would otherwise touch the real user config or notebooks
folder is redirected into tmp_path — the suite must never write to
``~/Library/Application Support/marimo-desktop`` or ``~/marimo notebooks``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from marimo_desktop import config


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the JSON prefs file at a throwaway location for every test."""
    path = tmp_path / "config" / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "_PATH", path)
    return path


@pytest.fixture(autouse=True)
def _no_notebooks_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stray MARIMO_DESKTOP_NOTEBOOKS in the dev shell must not leak in."""
    monkeypatch.delenv("MARIMO_DESKTOP_NOTEBOOKS", raising=False)
