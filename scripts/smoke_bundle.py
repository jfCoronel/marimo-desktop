#!/usr/bin/env python3
"""Run a built bundle for real and check marimo actually comes up.

The test suite covers the code; this covers the *artifact* — that ux produced
something that launches, finds its interpreter, and gets a marimo server
answering. Usage:

    python scripts/smoke_bundle.py dist/marimo-desktop.app
    python scripts/smoke_bundle.py dist/marimo-desktop          # Linux
    python scripts/smoke_bundle.py dist/marimo-desktop.exe      # Windows

Exits 0 when the bundle printed a working URL, 1 otherwise.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

READY_MARKER = "marimo is running at"


def executable_in(bundle: Path) -> Path:
    """The thing to actually exec — a .app is a directory, not a binary."""
    if bundle.suffix == ".app":
        inner = bundle / "Contents" / "MacOS"
        candidates = [p for p in inner.iterdir() if p.is_file() and os.access(p, os.X_OK)]
        if not candidates:
            msg = f"no executable inside {inner}"
            raise SystemExit(msg)
        return candidates[0]
    return bundle


def wait_for_url(proc: subprocess.Popen[str], log: Path, timeout: float) -> str | None:
    """Poll the log for the launcher's ready line (it may take a while: the
    first run of an ux bundle downloads its interpreter and wheels)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        text = log.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if READY_MARKER in line:
                return line.split(READY_MARKER, 1)[1].strip()
        if proc.poll() is not None:
            print(f"--- bundle exited with code {proc.returncode} ---\n{text}")
            return None
        time.sleep(1.0)
    print(
        f"--- no ready line after {timeout:.0f}s ---\n"
        f"{log.read_text(encoding='utf-8', errors='replace')}"
    )
    return None


def spawn_kwargs() -> dict[str, object]:
    """Put the child in its own process group so we can kill what it spawns."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def terminate_tree(proc: subprocess.Popen[str]) -> None:
    """Kill the launcher *and* the marimo server it started.

    Terminating only the launcher leaves marimo running: it holds the log file
    open (fatal to a temp-dir cleanup on Windows) and keeps whatever locks it
    inherited, which is how this stranded a CI runner's uv cache.
    """
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(  # noqa: S603
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],  # noqa: S607
            capture_output=True,
            check=False,
        )
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=10)


def http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310 (localhost)
            return response.status < 500
    except urllib.error.HTTPError:
        return True  # it answered; a redirect or 40x is still a live server
    except OSError as exc:
        print(f"could not reach {url}: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Path to the .app / binary ux produced")
    parser.add_argument("--timeout", type=float, default=420.0)
    args = parser.parse_args()

    if not args.bundle.exists():
        print(f"bundle not found: {args.bundle}")
        return 1

    exe = executable_in(args.bundle)
    print(f"launching {exe}")

    # ignore_cleanup_errors: on Windows a lingering handle must not turn a
    # successful smoke test into a failure.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        log_path = Path(tmp) / "bundle.log"
        log_path.touch()
        env = dict(
            os.environ,
            # Unbuffered: the launcher's print() would otherwise sit in a pipe
            # buffer and never reach the log while the process is still alive.
            PYTHONUNBUFFERED="1",
            # Never touch the real ~/marimo notebooks from a smoke test.
            MARIMO_DESKTOP_NOTEBOOKS=str(Path(tmp) / "notebooks"),
        )
        with log_path.open("w", encoding="utf-8") as log_file:
            proc = subprocess.Popen(  # noqa: S603
                [str(exe), "--headless", "--no-browser"],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env,
                text=True,
                **spawn_kwargs(),  # type: ignore[arg-type]
            )
            try:
                url = wait_for_url(proc, log_path, args.timeout)
                if url is None:
                    return 1
                print(f"bundle reports: {url}")
                if not http_ok(url):
                    return 1
                print("OK: the bundled marimo server answered")
                return 0
            finally:
                terminate_tree(proc)


if __name__ == "__main__":
    sys.exit(main())
