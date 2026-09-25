"""Manage a marimo server subprocess (start / poll readiness / stop)."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HOST = "127.0.0.1"

# Private flag: the app re-invoking itself as a marimo interpreter. See
# python_command() and launcher.main().
MARIMO_CLI_FLAG = "--exec-marimo-cli"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def python_command() -> list[str]:
    """The command prefix that runs marimo's CLI.

    Normally ``sys.executable -m marimo``. A Briefcase app has **no Python
    executable at all** — it embeds libpython and runs our package inside its
    own stub binary — so ``sys.executable`` there is the app itself, and
    passing it ``-m marimo`` just relaunches the app (recursively).

    Running marimo in-process instead is not enough: ``--sandbox`` hands
    ``sys.executable`` to ``uv run --python``, and multiprocessing spawns
    kernels from it, so marimo needs a real interpreter. The bundled uv
    provides one — same minor version, same marimo — as on Windows and
    Linux, where the first launch downloads it too. Without uv, the app
    re-invokes itself with a private flag and runs marimo's CLI in-process,
    which works for everything but the sandbox.
    """
    exe = Path(sys.executable)
    if exe.stem.lower().startswith("python"):
        return [str(exe), "-m", "marimo"]
    uv = bundled_uv()
    if uv is None:
        return [str(exe), MARIMO_CLI_FLAG]
    from importlib.metadata import version

    return [
        str(uv),
        "run",
        "--no-project",
        "--python",
        f"{sys.version_info.major}.{sys.version_info.minor}",
        "--with",
        f"marimo=={version('marimo')}",
        "--",
        "python",
        "-m",
        "marimo",
    ]


def bundled_uv() -> Path | None:
    """Locate a uv binary that travels with the app.

    Nothing on the user's machine can be relied on: an app launched from
    Finder gets a minimal PATH, and the interpreter we run on is one we
    shipped. Two places it can be, in order of preference:

    1. the ``uv`` wheel, which carries the binary — this is the one Briefcase
       installs into the bundle;
    2. next to the cached venv, where ux drops its own copy.
    """
    try:
        from uv import find_uv_bin

        packaged = Path(find_uv_bin())
        if packaged.is_file():
            return packaged
    except (ImportError, FileNotFoundError):
        pass

    name = "uv.exe" if sys.platform == "win32" else "uv"
    candidate = Path(sys.prefix).parent / name
    return candidate if candidate.is_file() else None


def child_env() -> dict[str, str]:
    """Environment for the marimo subprocess, with a usable package manager.

    Without this, installing a package from a notebook fails in the packaged
    app: marimo infers its package manager and, finding no `UV`, concludes
    "pip" because it is running inside a venv — but a uv-built venv has no
    pip, so the install dies. `UV` is the documented hook (marimo's
    find_uv_bin is `os.environ.get("UV", "uv")`), and PATH covers the
    `which("uv")` checks --sandbox makes.
    """
    env = dict(os.environ)
    uv = bundled_uv() or shutil.which("uv")
    if uv:
        env["UV"] = str(uv)
        env["PATH"] = os.pathsep.join([str(Path(uv).parent), env.get("PATH", "")])
    return env


def _record_path() -> Path:
    """Where a running server is recorded, so the next launch can find it."""
    from marimo_desktop.paths import config_dir

    return config_dir() / "server.json"


def _identity(pid: int) -> dict[str, float | int]:
    """PID plus creation time: a PID alone may since belong to something else."""
    import psutil

    return {"pid": pid, "created": psutil.Process(pid).create_time()}


def _is_alive(identity: dict[str, float | int]) -> bool:
    import psutil

    try:
        created = psutil.Process(int(identity["pid"])).create_time()
    except (psutil.Error, KeyError, TypeError, ValueError):
        return False
    return abs(created - float(identity["created"])) < 1.0


def _write_record(proc: subprocess.Popen[bytes], port: int) -> None:
    with contextlib.suppress(Exception):  # bookkeeping must never block a start
        record = {
            "server": _identity(proc.pid),
            "owner": _identity(os.getpid()),
            "port": port,
        }
        _record_path().write_text(json.dumps(record), encoding="utf-8")


def _clear_record() -> None:
    with contextlib.suppress(OSError):
        _record_path().unlink(missing_ok=True)


def reap_leftover_server(timeout: float = 5.0) -> bool:
    """Stop a server a previous run failed to stop; True if there was one.

    A clean Stop or window close takes the whole tree down, but a crash, a
    Force Quit or a logout gives us no chance: `uv run` and marimo (two of
    each, under --sandbox) are adopted by init and keep the port and the
    kernels' memory. So start() records the server, stop() erases the
    record, and a record found at the next start is a leftover.

    The server is only touched if it is still the exact process recorded
    (PID *and* creation time) and the app that started it is gone — another
    instance of the app may still be using it.
    """
    import psutil

    try:
        text = _record_path().read_text(encoding="utf-8")
    except OSError:
        return False
    try:
        record = json.loads(text)
    except ValueError:
        record = None
    if not isinstance(record, dict):
        _clear_record()
        return False
    try:
        if _is_alive(record.get("owner", {})) or not _is_alive(record.get("server", {})):
            return False
        root = psutil.Process(int(record["server"]["pid"]))
        # marimo's inner `uv run` starts its own session, so the process
        # group does not cover the tree; its parentage does.
        procs = [root, *root.children(recursive=True)]
        for proc in procs:
            with contextlib.suppress(psutil.Error):
                proc.terminate()
        _gone, alive = psutil.wait_procs(procs, timeout=timeout)
        for proc in alive:
            with contextlib.suppress(psutil.Error):
                proc.kill()
        psutil.wait_procs(alive, timeout=timeout)
        return True
    except (psutil.Error, KeyError, TypeError, ValueError):
        return False
    finally:
        # Whatever it pointed at, it is stale now — unless the owner is alive.
        if not _is_alive(record.get("owner", {})):
            _clear_record()


def _spawn_kwargs() -> dict[str, object]:
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _signal_group(proc: subprocess.Popen[bytes], *, hard: bool) -> None:
    """Stop the whole tree, not just the process we spawned."""
    if sys.platform == "win32":
        subprocess.run(  # noqa: S603
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],  # noqa: S607
            capture_output=True,
            check=False,
        )
        return
    sig = signal.SIGKILL if hard else signal.SIGTERM
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(os.getpgid(proc.pid), sig)


class MarimoServer:
    """A single ``marimo edit``/``marimo run`` process on a local port.

    Non-blocking: call :meth:`start`, then :meth:`poll` repeatedly (e.g. from a
    Tk ``after`` loop) until it returns ``"ready"`` or ``"exited"``.
    """

    def __init__(self, target: Path, mode: str = "edit", *, sandbox: bool = True) -> None:
        self.target = Path(target)
        self.mode = mode  # "edit" or "run"
        # Each notebook gets its own uv environment and records its
        # dependencies in its own file. Without this, packages a user installs
        # land in the bundle's cache venv, which a new app version replaces —
        # so every upgrade would silently lose them.
        self.sandbox = sandbox
        self.port: int | None = None
        self._proc: subprocess.Popen[bytes] | None = None

    @property
    def url(self) -> str:
        return f"http://{HOST}:{self.port}" if self.port else ""

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _command(self) -> list[str]:
        cmd = [
            *python_command(),
            self.mode,
            str(self.target),
            "--headless",
            "--host",
            HOST,
            "--port",
            str(self.port),
            "--no-token",
        ]
        if self.mode == "edit":
            cmd.append("--skip-update-check")
        if self.sandbox:
            cmd.append("--sandbox")
        return cmd

    def start(self) -> None:
        if self.running:
            msg = "server already running"
            raise RuntimeError(msg)
        reap_leftover_server()
        self.port = find_free_port()
        self._proc = subprocess.Popen(  # noqa: S603
            self._command(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=child_env(),
            # Own process group: in sandbox mode marimo re-launches itself
            # under `uv run` and spawns a kernel per notebook, so the process
            # we started is not the one holding the port. Terminating only it
            # would leave a live server behind after Stop.
            **_spawn_kwargs(),
        )
        _write_record(self._proc, self.port)

    def poll(self) -> str:
        """Return ``"starting"``, ``"ready"`` or ``"exited"``."""
        if self._proc is None:
            return "exited"
        if self._proc.poll() is not None:
            return "exited"
        try:
            with urllib.request.urlopen(self.url, timeout=1.0):  # noqa: S310 (local only)
                return "ready"
        except urllib.error.HTTPError:
            return "ready"  # answered; redirect/40x is fine
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            return "starting"

    def stop(self, timeout: float = 8.0) -> None:
        proc = self._proc
        if proc is None:
            return
        if proc.poll() is None:
            _signal_group(proc, hard=False)
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _signal_group(proc, hard=True)
                with contextlib.suppress(Exception):
                    proc.wait(timeout=timeout)
        _clear_record()
        self._proc = None
        self.port = None
