from __future__ import annotations

import ctypes
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk

from ..auth import Identity, read_session
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

        identity = read_session(db_path)
        if identity is None:
            self.show_login()
        else:
            self.show_main(identity)

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
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    _sync_windows_tk_scaling(root)
    root.minsize(900, 600)
    _center_window(root, 1120, 720)
    Application(root, db_path)
    root.mainloop()


def _enable_windows_dpi_awareness() -> None:
    """Prevent Windows from bitmap-scaling Tk on high-DPI displays."""
    if sys.platform != "win32":
        return

    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        set_context = user32.SetProcessDpiAwarenessContext
        set_context.argtypes = [ctypes.c_void_p]
        set_context.restype = ctypes.c_bool
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 == (HANDLE)-4
        if set_context(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass

    try:
        shcore = ctypes.WinDLL("shcore", use_last_error=True)
        set_awareness = shcore.SetProcessDpiAwareness
        set_awareness.argtypes = [ctypes.c_int]
        set_awareness.restype = ctypes.c_long
        # PROCESS_PER_MONITOR_DPI_AWARE == 2
        if set_awareness(2) == 0:
            return
    except (AttributeError, OSError):
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def _sync_windows_tk_scaling(root: tk.Tk) -> None:
    """Match Tk point-to-pixel scaling to the DPI of the current monitor."""
    if sys.platform != "win32":
        return

    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_dpi = user32.GetDpiForWindow
        get_dpi.argtypes = [ctypes.c_void_p]
        get_dpi.restype = ctypes.c_uint
        dpi = get_dpi(root.winfo_id())
        if dpi:
            root.tk.call("tk", "scaling", dpi / 72.0)
    except (AttributeError, OSError, tk.TclError):
        pass


def _center_window(root: tk.Tk, width: int, height: int) -> None:
    root.update_idletasks()
    x = max(0, (root.winfo_screenwidth() - width) // 2)
    y = max(0, (root.winfo_screenheight() - height) // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
