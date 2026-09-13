"""The JSON prefs file: round-trips, and never raising on a broken file."""

from __future__ import annotations

from pathlib import Path

from marimo_desktop import config


def test_load_returns_empty_when_the_file_is_missing() -> None:
    assert config.load() == {}


def test_set_then_get_round_trips() -> None:
    config.set("notebooks_dir", "/notebooks/nb")
    assert config.get("notebooks_dir") == "/notebooks/nb"


def test_get_returns_the_default_for_an_unknown_key() -> None:
    assert config.get("nope", "fallback") == "fallback"


def test_set_preserves_other_keys() -> None:
    config.set("a", 1)
    config.set("b", [2, 3])

    assert config.load() == {"a": 1, "b": [2, 3]}


def test_corrupt_json_reads_as_empty_instead_of_raising(_isolated_config: Path) -> None:
    _isolated_config.write_text("{not json", encoding="utf-8")

    assert config.load() == {}


def test_save_swallows_an_unwritable_path(monkeypatch, tmp_path: Path) -> None:
    """Prefs are a convenience: a read-only home must not crash the app."""
    monkeypatch.setattr(config, "_PATH", tmp_path / "missing-dir" / "config.json")

    config.save({"a": 1})  # must not raise

    assert config.load() == {}
