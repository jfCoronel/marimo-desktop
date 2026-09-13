"""Entry point.

Default: open the small Tk control window (:mod:`marimo_desktop.gui`).
``--headless``: start the server, open the browser, block — for automation.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import signal
import sys
import time

from marimo_desktop.browsers import open_url
from marimo_desktop.paths import config_dir as paths_config_dir
from marimo_desktop.paths import default_notebooks_dir
from marimo_desktop.server import MarimoServer

_STARTUP_TIMEOUT_S = 40.0


def _run_headless(*, notebook: str | None, mode: str, browser: bool) -> int:
    target = notebook or default_notebooks_dir()
    server = MarimoServer(target, mode=mode)
    server.start()

    def _shutdown(*_: object) -> None:
        with contextlib.suppress(Exception):
            server.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    deadline = time.monotonic() + _STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        state = server.poll()
        if state == "ready":
            print(f"marimo is running at {server.url}")
            if browser:
                open_url(server.url)
            break
        if state == "exited":
            print("marimo server exited before it was ready.", file=sys.stderr)
            return 1
        time.sleep(0.25)
    else:
        print(f"marimo did not become ready within {_STARTUP_TIMEOUT_S:.0f}s.", file=sys.stderr)

    try:
        while server.running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


# macOS hands a bundled app arguments of its own. `-psn_<n>` stands alone;
# the NS*/AppleLanguages ones come as `-flag value` pairs, so dropping only the
# flag leaves its value behind to be mistaken for the notebook positional.
_MACOS_FLAGS_WITH_VALUE = ("-NS", "-AppleLanguages")


def _strip_macos_args(argv: list[str]) -> list[str]:
    kept: list[str] = []
    drop_value = False
    for arg in argv:
        if drop_value:
            drop_value = False
            if not arg.startswith("-"):
                continue  # it was the flag's value; another flag isn't
        if arg.startswith("-psn_"):
            continue
        if arg.startswith(_MACOS_FLAGS_WITH_VALUE):
            drop_value = "=" not in arg
            continue
        kept.append(arg)
    return kept


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if os.environ.get("MARIMO_DESKTOP_DEBUG"):
        (paths_config_dir() / "argv.log").write_text(repr(sys.argv), encoding="utf-8")
    raw = _strip_macos_args(raw)

    parser = argparse.ArgumentParser(prog="marimo-desktop")
    parser.add_argument("notebook", nargs="?", help="Notebook file to open (implies --headless).")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="No window: start the server, open the browser, block.",
    )
    parser.add_argument(
        "--run", action="store_true", help="App mode (marimo run) instead of the editor."
    )
    parser.add_argument("--no-browser", action="store_true", help="Headless: don't open a browser.")
    args, _unknown = parser.parse_known_args(raw)

    if args.headless or args.notebook:
        return _run_headless(
            notebook=args.notebook,
            mode="run" if args.run else "edit",
            browser=not args.no_browser,
        )

    try:
        from marimo_desktop.gui import main as gui_main

        return gui_main()
    except Exception:  # noqa: BLE001 — launched from Finder, nowhere to print
        import traceback

        crash = paths_config_dir() / "crash.log"
        with contextlib.suppress(OSError):
            crash.write_text(traceback.format_exc(), encoding="utf-8")
        traceback.print_exc()
        print(f"GUI failed to start; falling back to headless. Details: {crash}", file=sys.stderr)
        return _run_headless(notebook=None, mode="edit", browser=True)


if __name__ == "__main__":
    raise SystemExit(main())
