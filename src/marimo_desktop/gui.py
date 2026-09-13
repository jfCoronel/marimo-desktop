"""A tiny Tk control window: pick a folder, start/stop marimo, open it.

Recent working folders are remembered too. New/open-notebook actions were
deliberately left out — marimo's own directory home page already covers
that (and recents) once you're inside a folder-wide session; see NOTES.md.
"""

from __future__ import annotations

import os
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from marimo_desktop import __version__, config
from marimo_desktop.browsers import open_url
from marimo_desktop.paths import default_notebooks_dir, ensure_notebooks_dir
from marimo_desktop.server import MarimoServer

_POLL_MS = 300
_STARTUP_TIMEOUT_S = 40
_MAX_RECENTS = 8
_COPYRIGHT_YEAR = 2026


def _uv_version() -> str:
    """`uv` writes its own version into every venv's pyvenv.cfg — read it
    from there instead of shelling out to an `uv` that may not be on PATH
    inside the packaged app."""
    cfg = Path(sys.prefix) / "pyvenv.cfg"
    try:
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("uv"):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return "?"


def _footer_text() -> str:
    try:
        marimo_version = version("marimo")
    except PackageNotFoundError:
        marimo_version = "?"
    runtime = f"Python {platform.python_version()} · uv {_uv_version()} · marimo {marimo_version}"
    return f"marimo desktop {__version__} · © {_COPYRIGHT_YEAR} jfCoronel\n{runtime}"


def _find_lib_dir(base_lib: Path, prefix: str, marker: str) -> Path | None:
    for cand in sorted(base_lib.glob(f"{prefix}[0-9]*"), reverse=True):
        if cand.is_dir() and (cand / marker).is_file():
            return cand
    return None


def _fix_tcl_tk_library_paths() -> None:
    """Point Tk at the Tcl/Tk library files it fails to find on its own.

    `uv`/`ux` build the app's venv by symlinking to a shared interpreter
    install (``sys.base_prefix``); tkinter's own search for ``tcl*``/``tk*``
    resolves against the venv (``sys.prefix``) instead, where those library
    folders don't exist — so plain `tk.Tk()` raises `TclError: Can't find a
    usable init.tcl`. Only matters inside a venv; harmless no-op otherwise.
    """
    if sys.prefix == sys.base_prefix:
        return
    base_lib = Path(sys.base_prefix) / "lib"
    if not base_lib.is_dir():
        return
    if "TCL_LIBRARY" not in os.environ:
        tcl_dir = _find_lib_dir(base_lib, "tcl", "init.tcl")
        if tcl_dir:
            os.environ["TCL_LIBRARY"] = str(tcl_dir)
    if "TK_LIBRARY" not in os.environ:
        tk_dir = _find_lib_dir(base_lib, "tk", "tk.tcl")
        if tk_dir:
            os.environ["TK_LIBRARY"] = str(tk_dir)


_fix_tcl_tk_library_paths()

import tkinter as tk  # noqa: E402 — must follow the library-path fix above
from tkinter import filedialog, ttk  # noqa: E402


def _add_recent(path: Path) -> None:
    """Push `path` to the front of the recent-folders list, keeping it unique."""
    recents = [p for p in config.get("recent_folders", []) if p != str(path)]
    recents.insert(0, str(path))
    config.set("recent_folders", recents[:_MAX_RECENTS])


def _shorten(path: Path, parts: int = 3) -> str:
    bits = path.parts
    return str(path) if len(bits) <= parts else ".../" + "/".join(bits[-parts:])


class App:
    def __init__(self) -> None:
        saved = config.get("notebooks_dir")
        self.folder: Path = ensure_notebooks_dir(Path(saved)) if saved else default_notebooks_dir()
        self.server: MarimoServer | None = None
        self._elapsed = 0.0
        _add_recent(self.folder)

        self.root = tk.Tk()
        self.root.title(f"marimo desktop {__version__}")
        self.root.resizable(width=False, height=False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        outer = ttk.Frame(self.root, padding=14)
        outer.grid(sticky="nsew")
        outer.columnconfigure(0, weight=1)

        # --- folder row ---------------------------------------------------
        folder_row = ttk.Frame(outer)
        folder_row.grid(row=0, column=0, sticky="ew")
        ttk.Label(folder_row, text="Folder:").grid(row=0, column=0, sticky="w")
        self.folder_var = tk.StringVar(value=_shorten(self.folder))
        ttk.Label(folder_row, textvariable=self.folder_var, foreground="#555").grid(
            row=0, column=1, sticky="w", padx=(6, 10)
        )
        self.change_btn = ttk.Button(folder_row, text="Change…", command=self._choose_folder)
        self.change_btn.grid(row=0, column=2, sticky="e")
        self.recent_btn = ttk.Menubutton(folder_row, text="Recent ▾")
        self.recent_menu = tk.Menu(
            self.recent_btn, tearoff=False, postcommand=self._build_recent_menu
        )
        self.recent_btn.config(menu=self.recent_menu)
        self.recent_btn.grid(row=0, column=3, sticky="e", padx=(6, 0))
        folder_row.columnconfigure(1, weight=1)

        # --- start / stop ----------------------------------------------------
        self.toggle_btn = ttk.Button(outer, text="▶  Start marimo", command=self._toggle)
        self.toggle_btn.grid(row=1, column=0, sticky="ew", pady=(12, 8))

        # --- server controls (enabled only while running) -------------------
        box = ttk.Frame(outer)
        box.grid(row=2, column=0, sticky="ew")
        box.columnconfigure(0, weight=1)

        self.url_var = tk.StringVar(value="—")
        self.url_label = tk.Label(box, textvariable=self.url_var, fg="#0a58ca", cursor="hand2")
        self.url_label.grid(row=0, column=0, sticky="w")
        self.url_label.bind("<Button-1>", lambda _e: self._open())

        self.copy_btn = ttk.Button(box, text="Copy URL", command=self._copy_url)
        self.copy_btn.grid(row=0, column=1, sticky="e", padx=(6, 0))

        # --- status ------------------------------------------------------
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(outer, textvariable=self.status_var, foreground="#777").grid(
            row=3, column=0, sticky="w", pady=(12, 0)
        )

        # --- footer: runtime versions + copyright -------------------------
        ttk.Label(
            outer,
            text=_footer_text(),
            foreground="#999",
            font=("TkDefaultFont", 9),
            justify="left",
        ).grid(row=4, column=0, sticky="w", pady=(10, 0))

        self._server_controls_enabled(enabled=False)
        self._bring_to_front()

    # -- lifecycle -------------------------------------------------------
    def run(self) -> int:
        self.root.mainloop()
        return 0

    def _bring_to_front(self) -> None:
        self.root.lift()
        self.root.attributes("-topmost", True)  # noqa: FBT003
        self.root.after(500, lambda: self.root.attributes("-topmost", False))  # noqa: FBT003
        if sys.platform == "darwin":
            self.root.after(50, self.root.focus_force)

    def _on_close(self) -> None:
        if self.server and self.server.running:
            self.status_var.set("Stopping the server…")
            self.root.update_idletasks()
            self.server.stop()
        self.root.destroy()

    # -- folder --------------------------------------------------------
    def _choose_folder(self) -> None:
        picked = filedialog.askdirectory(
            initialdir=str(self.folder), title="Choose the notebooks folder"
        )
        if not picked:
            return
        self._use_folder(Path(picked))

    def _use_folder(self, path: Path) -> None:
        self.folder = ensure_notebooks_dir(path)
        self.folder_var.set(_shorten(self.folder))
        config.set("notebooks_dir", str(self.folder))
        _add_recent(self.folder)

    def _build_recent_menu(self) -> None:
        self.recent_menu.delete(0, "end")
        stored = config.get("recent_folders", [])
        valid = [p for p in stored if Path(p).is_dir()]
        if valid != stored:
            config.set("recent_folders", valid)
        choices = [p for p in valid if Path(p) != self.folder]
        if not choices:
            self.recent_menu.add_command(label="(no recent folders)", state="disabled")
            return
        for raw in choices:
            path = Path(raw)
            self.recent_menu.add_command(
                label=_shorten(path), command=lambda p=path: self._use_folder(p)
            )

    # -- start / stop -------------------------------------------------
    def _toggle(self) -> None:
        if self.server and self.server.running:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        self.server = MarimoServer(self.folder, mode="edit")
        try:
            self.server.start()
        except OSError as exc:
            self.status_var.set(f"Couldn't start: {exc}")
            self.server = None
            return
        self._elapsed = 0.0
        self.toggle_btn.config(text="■  Stop")
        self.change_btn.config(state="disabled")
        self.recent_btn.config(state="disabled")
        self.status_var.set("Starting marimo…")
        self.root.after(_POLL_MS, self._tick)

    def _stop(self) -> None:
        if self.server:
            self.server.stop()
            self.server = None
        self.toggle_btn.config(text="▶  Start marimo")
        self.change_btn.config(state="normal")
        self.recent_btn.config(state="normal")
        self.url_var.set("—")
        self._server_controls_enabled(enabled=False)
        self.status_var.set("Server stopped.")

    def _tick(self) -> None:
        if not self.server:
            return
        state = self.server.poll()
        if state == "ready":
            self.url_var.set(self.server.url)
            self._server_controls_enabled(enabled=True)
            self.status_var.set(f"marimo ready in {self._elapsed:.1f}s. Click the link to open it.")
            return
        if state == "exited":
            self.status_var.set("marimo exited before it was ready.")
            self._stop()
            return
        self._elapsed += _POLL_MS / 1000
        if self._elapsed >= _STARTUP_TIMEOUT_S:
            self.status_var.set(f"No response after {_STARTUP_TIMEOUT_S}s. Stopping.")
            self._stop()
            return
        self.root.after(_POLL_MS, self._tick)

    # -- running actions --------------------------------------------
    def _server_controls_enabled(self, *, enabled: bool) -> None:
        self.copy_btn.config(state="normal" if enabled else "disabled")
        self.url_label.config(cursor="hand2" if enabled else "")

    def _open(self) -> None:
        if self.server and self.server.running:
            open_url(self.server.url)

    def _copy_url(self) -> None:
        if not (self.server and self.server.running):
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.server.url)
        self.status_var.set("URL copied to clipboard.")


def main() -> int:
    return App().run()
