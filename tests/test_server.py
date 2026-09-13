"""MarimoServer: command construction, readiness polling, teardown.

No real marimo process is started — that would make the suite slow and
network/port dependent. The subprocess handling itself is exercised with a
cheap `python -c sleep` stand-in.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

from marimo_desktop import server as server_mod
from marimo_desktop.server import HOST, MarimoServer, find_free_port


def test_find_free_port_is_bindable() -> None:
    port = find_free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, port))  # would raise if the port weren't actually free


def test_url_is_empty_until_started(tmp_path: Path) -> None:
    assert MarimoServer(tmp_path).url == ""


def test_url_uses_loopback_only(tmp_path: Path) -> None:
    srv = MarimoServer(tmp_path)
    srv.port = 4242
    assert srv.url == "http://127.0.0.1:4242"


def test_edit_command_shape(tmp_path: Path) -> None:
    srv = MarimoServer(tmp_path)
    srv.port = 4242
    cmd = srv._command()

    assert cmd[:4] == [sys.executable, "-m", "marimo", "edit"]
    assert cmd[4] == str(tmp_path)
    # Never bind a public interface, never hand out a tokenless public server.
    assert "--headless" in cmd
    assert cmd[cmd.index("--host") + 1] == HOST
    assert cmd[cmd.index("--port") + 1] == "4242"
    assert "--no-token" in cmd
    assert "--skip-update-check" in cmd


def test_run_mode_skips_update_check(tmp_path: Path) -> None:
    srv = MarimoServer(tmp_path, mode="run")
    srv.port = 4242
    cmd = srv._command()

    assert cmd[3] == "run"
    # `marimo run` has no --skip-update-check flag; passing it would error out.
    assert "--skip-update-check" not in cmd


def test_poll_reports_exited_before_start(tmp_path: Path) -> None:
    assert MarimoServer(tmp_path).poll() == "exited"


def test_poll_reports_starting_while_connection_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    srv = MarimoServer(tmp_path)
    srv.port = 4242
    srv._proc = _FakeProc(alive=True)

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(server_mod.urllib.request, "urlopen", _refuse)
    assert srv.poll() == "starting"


def test_poll_counts_an_http_error_as_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 404/redirect still means the server answered — that's ready enough."""
    srv = MarimoServer(tmp_path)
    srv.port = 4242
    srv._proc = _FakeProc(alive=True)

    def _http_error(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.HTTPError(srv.url, 404, "Not Found", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(server_mod.urllib.request, "urlopen", _http_error)
    assert srv.poll() == "ready"


def test_poll_reports_exited_when_the_process_dies(tmp_path: Path) -> None:
    srv = MarimoServer(tmp_path)
    srv.port = 4242
    srv._proc = _FakeProc(alive=False)
    assert srv.poll() == "exited"


def test_start_refuses_to_double_start(tmp_path: Path) -> None:
    srv = MarimoServer(tmp_path)
    srv._proc = _FakeProc(alive=True)
    with pytest.raises(RuntimeError, match="already running"):
        srv.start()


def test_stop_terminates_the_process_and_clears_state(tmp_path: Path) -> None:
    srv = MarimoServer(tmp_path)
    srv.port = 4242
    srv._proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    proc = srv._proc
    assert srv.running

    srv.stop(timeout=10.0)

    assert proc.poll() is not None, "the child process should be dead"
    assert srv._proc is None
    assert srv.port is None
    assert not srv.running


def test_stop_is_a_no_op_when_never_started(tmp_path: Path) -> None:
    MarimoServer(tmp_path).stop()  # must not raise


class _FakeProc:
    """Minimal stand-in for Popen: only `poll()` is ever consulted here."""

    def __init__(self, *, alive: bool) -> None:
        self._alive = alive

    def poll(self) -> int | None:
        return None if self._alive else 1


# -- package manager for the marimo child ---------------------------------


def test_bundled_uv_found_next_to_the_venv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ux drops its uv beside the cached venv, never on PATH."""
    uv = tmp_path / ("uv.exe" if sys.platform == "win32" else "uv")
    uv.touch()
    monkeypatch.setattr(sys, "prefix", str(tmp_path / ".venv"))

    assert server_mod.bundled_uv() == uv


def test_bundled_uv_absent_in_a_dev_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "prefix", str(tmp_path / ".venv"))

    assert server_mod.bundled_uv() is None


def test_child_env_points_marimo_at_the_bundled_uv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: without UV, marimo infers "pip" because it is inside a venv,
    but a uv-built venv has no pip — so installing a package from a notebook
    failed in the packaged app."""
    uv = tmp_path / ("uv.exe" if sys.platform == "win32" else "uv")
    uv.touch()
    monkeypatch.setattr(sys, "prefix", str(tmp_path / ".venv"))

    env = server_mod.child_env()

    assert env["UV"] == str(uv)
    assert env["PATH"].split(os.pathsep)[0] == str(tmp_path)


def test_child_env_falls_back_to_uv_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "prefix", str(tmp_path / ".venv"))
    monkeypatch.setattr(server_mod.shutil, "which", lambda _: "/somewhere/bin/uv")

    assert server_mod.child_env()["UV"] == "/somewhere/bin/uv"


def test_child_env_without_any_uv_is_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "prefix", str(tmp_path / ".venv"))
    monkeypatch.setattr(server_mod.shutil, "which", lambda _: None)
    monkeypatch.delenv("UV", raising=False)

    assert "UV" not in server_mod.child_env()
