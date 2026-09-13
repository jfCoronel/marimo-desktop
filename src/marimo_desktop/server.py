"""Manage a marimo server subprocess (start / poll readiness / stop)."""

from __future__ import annotations

import contextlib
import os
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HOST = "127.0.0.1"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def bundled_uv() -> Path | None:
    """The `uv` ux ships inside the bundle, next to the cached venv.

    ux puts it there but never on PATH, and an app launched from Finder gets
    a minimal PATH anyway.
    """
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


class MarimoServer:
    """A single ``marimo edit``/``marimo run`` process on a local port.

    Non-blocking: call :meth:`start`, then :meth:`poll` repeatedly (e.g. from a
    Tk ``after`` loop) until it returns ``"ready"`` or ``"exited"``.
    """

    def __init__(self, target: Path, mode: str = "edit") -> None:
        self.target = Path(target)
        self.mode = mode  # "edit" or "run"
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
            sys.executable,
            "-m",
            "marimo",
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
        return cmd

    def start(self) -> None:
        if self.running:
            msg = "server already running"
            raise RuntimeError(msg)
        self.port = find_free_port()
        self._proc = subprocess.Popen(  # noqa: S603
            self._command(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=child_env(),
        )

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
            proc.terminate()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                with contextlib.suppress(Exception):
                    proc.wait(timeout=timeout)
        self._proc = None
        self.port = None
