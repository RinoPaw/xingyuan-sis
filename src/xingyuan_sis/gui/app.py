from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from ..auth import Identity
from .login import LoginView
from .main_window import MainWindow
from .theme import configure_styles


class Application:
    """Own the Tk root and swap top-level application views."""

    def __init__(self, root: tk.Tk, db_path: Path | str | None = None) -> None:
        self.root = root
        self.db_path = db_path
        self.current_view: ttk.Frame | None = None
        configure_styles(root)
        self.show_login()

    def show_login(self) -> None:
        self.root.title("星原 SIS · 登录")
        self.root.configure(menu="")
        self._mount(LoginView(self.root, self.db_path, on_success=self.show_main))

    def show_main(self, identity: Identity) -> None:
        self.root.title("星原 SIS")
        self._mount(
            MainWindow(
                self.root,
                self.db_path,
                identity,
                on_logout=self.show_login,
            )
        )

    def _mount(self, view: ttk.Frame) -> None:
        if self.current_view is not None:
            self.current_view.destroy()
        self.current_view = view
        self.current_view.pack(fill="both", expand=True)


def run(db_path: Path | str | None = None) -> None:
    root = tk.Tk()
    root.minsize(900, 600)
    _center_window(root, 1120, 720)
    Application(root, db_path)
    root.mainloop()


def _center_window(root: tk.Tk, width: int, height: int) -> None:
    root.update_idletasks()
    x = max(0, (root.winfo_screenwidth() - width) // 2)
    y = max(0, (root.winfo_screenheight() - height) // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
