"""Entry point: argv handling, headless wiring, and the Finder crash fallback."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from marimo_desktop import launcher


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Record _run_headless invocations instead of starting a server."""
    recorded: list[dict] = []

    def _fake(*, notebook: str | None, mode: str, browser: bool) -> int:
        recorded.append({"notebook": notebook, "mode": mode, "browser": browser})
        return 0

    monkeypatch.setattr(launcher, "_run_headless", _fake)
    return recorded


def _stub_gui(monkeypatch: pytest.MonkeyPatch, main) -> None:
    """Swap in a fake marimo_desktop.gui so no Tk window is ever created."""
    module = types.ModuleType("marimo_desktop.gui")
    module.main = main
    monkeypatch.setitem(sys.modules, "marimo_desktop.gui", module)


def test_headless_flag_starts_the_editor(calls: list[dict]) -> None:
    assert launcher.main(["--headless"]) == 0
    assert calls == [{"notebook": None, "mode": "edit", "browser": True}]


def test_a_notebook_argument_implies_headless(calls: list[dict]) -> None:
    launcher.main(["notebooks/welcome.py"])
    assert calls == [{"notebook": "notebooks/welcome.py", "mode": "edit", "browser": True}]


def test_run_flag_selects_app_mode(calls: list[dict]) -> None:
    launcher.main(["--headless", "--run"])
    assert calls[0]["mode"] == "run"


def test_no_browser_flag(calls: list[dict]) -> None:
    launcher.main(["--headless", "--no-browser"])
    assert calls[0]["browser"] is False


def test_macos_process_serial_number_args_are_ignored(
    calls: list[dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finder hands a bundled app -psn_/-NS args; they must not look like a notebook."""
    opened: list[bool] = []
    _stub_gui(monkeypatch, lambda: opened.append(True) or 0)

    launcher.main(
        ["-psn_0_1234567", "-NSDocumentRevisionsDebugMode", "YES", "-AppleLanguages", "(en)"]
    )

    assert opened == [True], "should have opened the window, not a phantom notebook"
    assert calls == []


def test_no_args_opens_the_window(calls: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_gui(monkeypatch, lambda: 0)

    assert launcher.main([]) == 0
    assert calls == []


def test_a_crashing_gui_falls_back_to_headless_and_logs(
    calls: list[dict], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Launched from Finder there's no console, so the traceback must hit a file."""

    def _boom() -> int:
        msg = "no display"
        raise RuntimeError(msg)

    _stub_gui(monkeypatch, _boom)
    monkeypatch.setattr(launcher, "paths_config_dir", lambda: tmp_path)

    assert launcher.main([]) == 0
    assert calls == [{"notebook": None, "mode": "edit", "browser": True}]
    crash = (tmp_path / "crash.log").read_text(encoding="utf-8")
    assert "RuntimeError: no display" in crash


def test_unknown_flags_do_not_abort(calls: list[dict]) -> None:
    """argparse would SystemExit on an unknown flag; parse_known_args must not."""
    launcher.main(["--headless", "--totally-unknown"])
    assert calls[0]["notebook"] is None


# -- macOS argv noise -----------------------------------------------------


def test_strip_drops_the_process_serial_number() -> None:
    assert launcher._strip_macos_args(["-psn_0_1234567", "--headless"]) == ["--headless"]


def test_strip_drops_ns_flags_together_with_their_values() -> None:
    """The value is the trap: `-AppleLanguages (en)` used to leave `(en)` behind."""
    argv = ["-NSDocumentRevisionsDebugMode", "YES", "-AppleLanguages", "(en)"]

    assert launcher._strip_macos_args(argv) == []


def test_strip_handles_the_equals_form_without_eating_the_next_arg() -> None:
    assert launcher._strip_macos_args(["-AppleLanguages=(en)", "nb.py"]) == ["nb.py"]


def test_strip_leaves_real_arguments_untouched() -> None:
    argv = ["notebooks/welcome.py", "--headless", "--run"]

    assert launcher._strip_macos_args(argv) == argv


def test_strip_does_not_swallow_a_flag_that_follows_a_valueless_ns_flag() -> None:
    assert launcher._strip_macos_args(["-NSSomething", "--headless"]) == ["--headless"]
