#!/usr/bin/env python3
"""Print a Briefcase `-C` override that makes `requires` exactly our list.

Briefcase *adds* [project].dependencies to [tool.briefcase...].requires, so
there is no way to leave marimo out from the config alone — and the ux
builds need it there. The Briefcase app doesn't: it runs the marimo uv
installs. So the workflows pass the list as a replacement:

    briefcase create macOS -C "$(python scripts/briefcase_requires.py)"
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def requires() -> list[str]:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return config["tool"]["briefcase"]["app"]["marimo-desktop"]["requires"]


def override() -> str:
    # A JSON array of strings is also a valid TOML array.
    return f"requires={json.dumps(requires())}"


if __name__ == "__main__":
    print(override())
