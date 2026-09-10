"""A tiny Tk control window: pick a folder, start/stop marimo, open it.

Notebook creation / browsing is deliberately out of scope for v1 — see README.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from marimo_desktop import config
from marimo_desktop.browsers import DEFAULT_LABEL, available_browsers, open_url
from marimo_desktop.paths import default_notebooks_dir, ensure_notebooks_dir
from marimo_desktop.server import MarimoServer

_POLL_MS = 300
_STARTUP_TIMEOUT_S = 40


def _shorten(path: Path, parts: int = 3) -> str:
    bits = path.parts
    return str(path) if len(bits) <= parts else ".../" + "/".join(bits[-parts:])


class App:
    def __init__(self) -> None:
        saved = config.get("notebooks_dir")
        self.folder: Path = (
            ensure_notebooks_dir(Path(saved)) if saved else default_notebooks_dir()
        )
        self.server: MarimoServer | None = None
        self._elapsed = 0.0

        self.root = tk.Tk()
        self.root.title("marimo desktop")
        self.root.resizable(width=False, height=False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        outer = ttk.Frame(self.root, padding=14)
        outer.grid(sticky="nsew")
        outer.columnconfigure(0, weight=1)

        # --- folder row ---------------------------------------------------
        folder_row = ttk.Frame(outer)
        folder_row.grid(row=0, column=0, sticky="ew")
        ttk.Label(folder_row, text="Carpeta:").grid(row=0, column=0, sticky="w")
        self.folder_var = tk.StringVar(value=_shorten(self.folder))
        ttk.Label(folder_row, textvariable=self.folder_var, foreground="#555").grid(
            row=0, column=1, sticky="w", padx=(6, 10)
        )
        self.change_btn = ttk.Button(folder_row, text="Cambiar…", command=self._choose_folder)
        self.change_btn.grid(row=0, column=2, sticky="e")
        folder_row.columnconfigure(1, weight=1)

        # --- start / stop ----------------------------------------------------
        self.toggle_btn = ttk.Button(outer, text="▶  Arrancar marimo", command=self._toggle)
        self.toggle_btn.grid(row=1, column=0, sticky="ew", pady=(12, 8))

        # --- server controls (enabled only while running) -------------------
        box = ttk.Frame(outer)
        box.grid(row=2, column=0, sticky="ew")
        box.columnconfigure(1, weight=1)

        self.url_var = tk.StringVar(value="—")
        self.url_label = tk.Label(box, textvariable=self.url_var, fg="#0a58ca", cursor="hand2")
        self.url_label.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self.url_label.bind("<Button-1>", lambda _e: self._open())

        ttk.Label(box, text="Navegador:").grid(row=1, column=0, sticky="w")
        self.browser_var = tk.StringVar(value=config.get("browser", DEFAULT_LABEL))
        choices = available_browsers()
        if self.browser_var.get() not in choices:
            self.browser_var.set(DEFAULT_LABEL)
        self.browser_menu = ttk.OptionMenu(
            box, self.browser_var, self.browser_var.get(), *choices, command=self._remember_browser
        )
        self.browser_menu.grid(row=1, column=1, sticky="w", padx=6)

        btns = ttk.Frame(box)
        btns.grid(row=1, column=2, sticky="e")
        self.open_btn = ttk.Button(btns, text="Abrir", command=self._open)
        self.open_btn.grid(row=0, column=0)
        self.copy_btn = ttk.Button(btns, text="Copiar URL", command=self._copy_url)
        self.copy_btn.grid(row=0, column=1, padx=(6, 0))

        # --- status ------------------------------------------------------
        self.status_var = tk.StringVar(value="Listo.")
        ttk.Label(outer, textvariable=self.status_var, foreground="#777").grid(
            row=3, column=0, sticky="w", pady=(12, 0)
        )

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
            self.status_var.set("Parando el servidor…")
            self.root.update_idletasks()
            self.server.stop()
        self.root.destroy()

    # -- folder --------------------------------------------------------
    def _choose_folder(self) -> None:
        picked = filedialog.askdirectory(
            initialdir=str(self.folder), title="Elige la carpeta de notebooks"
        )
        if not picked:
            return
        self.folder = ensure_notebooks_dir(Path(picked))
        self.folder_var.set(_shorten(self.folder))
        config.set("notebooks_dir", str(self.folder))

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
            self.status_var.set(f"No se pudo arrancar: {exc}")
            self.server = None
            return
        self._elapsed = 0.0
        self.toggle_btn.config(text="■  Parar")
        self.change_btn.config(state="disabled")
        self.status_var.set("Arrancando marimo…")
        self.root.after(_POLL_MS, self._tick)

    def _stop(self) -> None:
        if self.server:
            self.server.stop()
            self.server = None
        self.toggle_btn.config(text="▶  Arrancar marimo")
        self.change_btn.config(state="normal")
        self.url_var.set("—")
        self._server_controls_enabled(enabled=False)
        self.status_var.set("Servidor parado.")

    def _tick(self) -> None:
        if not self.server:
            return
        state = self.server.poll()
        if state == "ready":
            self.url_var.set(self.server.url)
            self._server_controls_enabled(enabled=True)
            self.status_var.set(f"marimo listo en {self._elapsed:.1f}s.")
            self._open()
            return
        if state == "exited":
            self.status_var.set("marimo se cerró antes de estar listo.")
            self._stop()
            return
        self._elapsed += _POLL_MS / 1000
        if self._elapsed >= _STARTUP_TIMEOUT_S:
            self.status_var.set(f"Sin respuesta tras {_STARTUP_TIMEOUT_S}s. Parando.")
            self._stop()
            return
        self.root.after(_POLL_MS, self._tick)

    # -- running actions --------------------------------------------
    def _server_controls_enabled(self, *, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for widget in (self.browser_menu, self.open_btn, self.copy_btn):
            widget.config(state=state)
        self.url_label.config(cursor="hand2" if enabled else "")

    def _open(self) -> None:
        if self.server and self.server.running:
            open_url(self.server.url, self.browser_var.get())

    def _copy_url(self) -> None:
        if not (self.server and self.server.running):
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.server.url)
        self.status_var.set("URL copiada al portapapeles.")

    def _remember_browser(self, value: str) -> None:
        config.set("browser", value)


def main() -> int:
    return App().run()
