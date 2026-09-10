"""Detect installed browsers and open a URL in a chosen one.

``webbrowser`` only knows the system default; to send the URL to a *specific*
browser we shell out (``open -a`` on macOS, the binary directly on Linux).
Everything falls back to the default browser on any failure.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

DEFAULT_LABEL = "Predeterminado"

# macOS: display name -> .app bundle name (what `open -a` expects)
_MACOS_APPS = {
    "Safari": "Safari",
    "Google Chrome": "Google Chrome",
    "Firefox": "Firefox",
    "Microsoft Edge": "Microsoft Edge",
    "Brave": "Brave Browser",
    "Arc": "Arc",
    "Vivaldi": "Vivaldi",
    "Opera": "Opera",
}

# Linux: display name -> candidate executables
_LINUX_BINS = {
    "Firefox": ["firefox"],
    "Google Chrome": ["google-chrome", "google-chrome-stable"],
    "Chromium": ["chromium", "chromium-browser"],
    "Brave": ["brave-browser", "brave"],
    "Microsoft Edge": ["microsoft-edge", "microsoft-edge-stable"],
}


def _macos_detected() -> dict[str, str]:
    roots = [Path("/Applications"), Path.home() / "Applications"]
    found: dict[str, str] = {}
    for label, app in _MACOS_APPS.items():
        if any((root / f"{app}.app").exists() for root in roots):
            found[label] = app
    return found


def _linux_detected() -> dict[str, str]:
    found: dict[str, str] = {}
    for label, candidates in _LINUX_BINS.items():
        for exe in candidates:
            path = shutil.which(exe)
            if path:
                found[label] = path
                break
    return found


def _detected() -> dict[str, str]:
    if sys.platform == "darwin":
        return _macos_detected()
    if sys.platform.startswith("linux"):
        return _linux_detected()
    return {}


def available_browsers() -> list[str]:
    """Labels for the picker: the default, then any specific browsers found."""
    return [DEFAULT_LABEL, *sorted(_detected())]


def open_url(url: str, label: str | None = None) -> None:
    if label and label != DEFAULT_LABEL:
        target = _detected().get(label)
        if target:
            try:
                if sys.platform == "darwin":
                    subprocess.Popen(["open", "-a", target, url])  # noqa: S603, S607
                else:
                    subprocess.Popen([target, url])  # noqa: S603
                return
            except OSError:
                pass  # fall through to default
    webbrowser.open(url)
