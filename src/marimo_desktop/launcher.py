"""Entry point.

Default: open the small Tk control window (:mod:`marimo_desktop.gui`).
``--headless``: start the server, open the browser, block — for automation.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from marimo_desktop.browsers import open_url
from marimo_desktop.paths import config_dir as paths_config_dir
from marimo_desktop.paths import default_notebooks_dir
from marimo_desktop.server import (
    MarimoServer,
    bundled_uv,
    child_env,
    has_interpreter,
    reap_leftover_server,
    uv_python_command,
)

_STARTUP_TIMEOUT_S = 40.0


def _publish_url(url: str) -> None:
    """Write the URL where a test harness can read it.

    Printing is not enough everywhere: a Briefcase app runs under a stub that
    does not forward stdout, so the smoke test has no other way to learn which
    port marimo picked. No-op unless the variable is set.
    """
    target = os.environ.get("MARIMO_DESKTOP_URL_FILE")
    if not target:
        return
    with contextlib.suppress(OSError):
        Path(target).write_text(url, encoding="utf-8")


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
            _publish_url(server.url)
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


# Interpreter flags multiprocessing prepends (util._args_from_interpreter_flags)
# and the ones among them that take a separate value.
_PYTHON_FLAGS = {"-B", "-s", "-S", "-E", "-I", "-O", "-OO", "-b", "-bb", "-q", "-u", "-v"}
_PYTHON_VALUE_FLAGS = {"-X", "-W"}


def _python_c_command(args: list[str]) -> tuple[str, list[str]] | None:
    """Recognise ``[flags...] -c CODE [args...]`` and return (CODE, args).

    A Briefcase app has no Python executable, so ``sys.executable`` is the app
    and anything treating it as one — multiprocessing, uv probing an
    interpreter — launches ``<app> -B -s -c "..."``. Answering like Python
    makes uv build environments on a stub that cannot run outside the bundle
    (and then hang); ignoring it opens another control window. So refuse.
    """
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "-c" and i + 1 < len(args):
            return args[i + 1], args[i + 2 :]
        if arg in _PYTHON_VALUE_FLAGS:
            i += 2
        elif arg in _PYTHON_FLAGS or (arg[:2] in _PYTHON_VALUE_FLAGS and len(arg) > 2):
            i += 1
        else:
            return None
    return None


# Set in the interpreter uv provides, so it never tries to relaunch again.
_RELAUNCHED_ENV = "MARIMO_DESKTOP_RELAUNCHED"


def _has_tkinter() -> bool:
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return False
    return True


def _runtime_marker() -> Path:
    from marimo_desktop import __version__

    return paths_config_dir() / f"runtime-{__version__}.ready"


def _notify_first_run() -> None:
    """The first relaunch downloads Python and marimo with no window to show
    for it; say so, or the app looks like it did nothing for minutes."""
    if sys.platform != "darwin" or _runtime_marker().exists():
        return
    script = (
        'display notification "Downloading Python and marimo. This happens once '
        'and can take a few minutes." with title "marimo desktop"'
    )
    with contextlib.suppress(OSError):
        subprocess.Popen(  # noqa: S603
            ["/usr/bin/osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _relaunch_under_uv(args: list[str]) -> None:
    """Replace this process with the same app on a Python that has tkinter.

    A Briefcase app embeds a Python without tkinter (and without Tcl/Tk), so
    the control window cannot open in it. The interpreter uv provides has
    both, and the server already runs on it; so the window does too. The
    code is the same: our package is put on PYTHONPATH from the bundle.
    Returns only if there is no uv to do it with.
    """
    uv = bundled_uv()
    if uv is None:
        return
    from importlib.metadata import version

    import marimo_desktop

    env = child_env()
    env[_RELAUNCHED_ENV] = "1"
    package_root = str(Path(marimo_desktop.__file__).resolve().parent.parent)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [package_root, env.get("PYTHONPATH")]))
    # Importing from the bundle must not write __pycache__ into it: any file
    # added to a signed .app invalidates its signature.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [
        *uv_python_command(uv, f"psutil=={version('psutil')}"),
        "-m",
        "marimo_desktop",
        *args,
    ]
    _notify_first_run()
    os.execve(uv, cmd, env)  # noqa: S606


def _needs_relaunch() -> bool:
    return not has_interpreter() and not os.environ.get(_RELAUNCHED_ENV) and not _has_tkinter()


def _check_gui() -> int:
    """CI: prove the control window's toolkit loads, without a display."""
    import tkinter

    import marimo_desktop.gui  # noqa: F401 — runs the Tcl/Tk path fix

    tkinter.Tcl().eval("info patchlevel")
    print("gui ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if _python_c_command(raw) is not None:
        print("marimo desktop is not a Python interpreter.", file=sys.stderr)
        return 1
    if os.environ.get("MARIMO_DESKTOP_DEBUG"):
        (paths_config_dir() / "argv.log").write_text(repr(sys.argv), encoding="utf-8")
    raw = _strip_macos_args(raw)
    # A server a crashed run left behind would hold its port and memory
    # until logout; clear it now rather than when Start is next pressed.
    reap_leftover_server()

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
    parser.add_argument("--check-gui", action="store_true", help=argparse.SUPPRESS)
    args, _unknown = parser.parse_known_args(raw)

    if args.headless or args.notebook:
        return _run_headless(
            notebook=args.notebook,
            mode="run" if args.run else "edit",
            browser=not args.no_browser,
        )

    if _needs_relaunch():
        _relaunch_under_uv(raw)
    if args.check_gui:
        return _check_gui()
    if os.environ.get(_RELAUNCHED_ENV):
        with contextlib.suppress(OSError):
            _runtime_marker().touch()
        # Both only concern this process (sys.path and sys.dont_write_bytecode
        # are already set); the server and its kernels must not inherit them.
        os.environ.pop("PYTHONPATH", None)
        os.environ.pop("PYTHONDONTWRITEBYTECODE", None)

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
