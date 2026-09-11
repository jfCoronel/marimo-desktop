"""Open a URL in the system's default browser."""

from __future__ import annotations

import webbrowser


def open_url(url: str) -> None:
    webbrowser.open(url)
