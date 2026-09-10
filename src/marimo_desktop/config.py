"""Tiny JSON preferences file — no dependencies."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from marimo_desktop.paths import config_dir

_PATH = config_dir() / "config.json"


def load() -> dict[str, Any]:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(data: dict[str, Any]) -> None:
    try:
        _PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def get(key: str, default: Any = None) -> Any:
    return load().get(key, default)


def set(key: str, value: Any) -> None:  # noqa: A001 (deliberate small API)
    data = load()
    data[key] = value
    save(data)


def config_path() -> Path:
    return _PATH
