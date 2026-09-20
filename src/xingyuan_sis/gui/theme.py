from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

BACKGROUND = "#f4f6f8"
SURFACE = "#ffffff"
SIDEBAR = "#172033"
SIDEBAR_HOVER = "#22304a"
SIDEBAR_SELECTED = "#2d4164"
TEXT = "#1d2735"
MUTED = "#667085"
BORDER = "#dfe4ea"
ACCENT = "#356ae6"
ACCENT_ACTIVE = "#2856bd"
ERROR = "#c63d4f"
SUCCESS = "#2f7d4c"


def configure_styles(root: tk.Misc) -> ttk.Style:
    """Apply the small design system shared by the GUI frontend."""
    family = _preferred_font(root)
    for name, size in (
        ("TkDefaultFont", 10),
        ("TkTextFont", 10),
        ("TkMenuFont", 10),
        ("TkHeadingFont", 10),
    ):
        tkfont.nametofont(name).configure(family=family, size=size)

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    root.configure(background=BACKGROUND)

    style.configure("App.TFrame", background=BACKGROUND)
    style.configure("Surface.TFrame", background=SURFACE)
    style.configure("Sidebar.TFrame", background=SIDEBAR)
    style.configure("Topbar.TFrame", background=SURFACE)
    style.configure("Card.TFrame", background=SURFACE, relief="flat")

    style.configure(
        "Title.TLabel",
        background=BACKGROUND,
        foreground=TEXT,
        font=(family, 22, "bold"),
    )
    style.configure(
        "SectionTitle.TLabel",
        background=BACKGROUND,
        foreground=TEXT,
        font=(family, 15, "bold"),
    )
    style.configure(
        "Body.TLabel",
        background=BACKGROUND,
        foreground=TEXT,
        font=(family, 10),
    )
    style.configure(
        "Muted.TLabel",
        background=BACKGROUND,
        foreground=MUTED,
        font=(family, 9),
    )
    style.configure(
        "Surface.TLabel",
        background=SURFACE,
        foreground=TEXT,
        font=(family, 10),
    )
    style.configure(
        "SurfaceMuted.TLabel",
        background=SURFACE,
        foreground=MUTED,
        font=(family, 9),
    )
    style.configure(
        "SidebarTitle.TLabel",
        background=SIDEBAR,
        foreground="#ffffff",
        font=(family, 18, "bold"),
    )
    style.configure(
        "SidebarMuted.TLabel",
        background=SIDEBAR,
        foreground="#9eabc0",
        font=(family, 9),
    )
    style.configure(
        "LoginHeroTitle.TLabel",
        background=SIDEBAR,
        foreground="#ffffff",
        font=(family, 24, "bold"),
    )
    style.configure(
        "LoginHeroBody.TLabel",
        background=SIDEBAR,
        foreground="#b8c3d5",
        font=(family, 10),
    )
    style.configure(
        "LoginTitle.TLabel",
        background=SURFACE,
        foreground=TEXT,
        font=(family, 20, "bold"),
    )
    style.configure(
        "Status.TLabel",
        background=SURFACE,
        foreground=SUCCESS,
        font=(family, 9),
    )
    style.configure(
        "Error.TLabel",
        background=SURFACE,
        foreground=ERROR,
        font=(family, 9),
    )
    style.configure(
        "CardValue.TLabel",
        background=SURFACE,
        foreground=TEXT,
        font=(family, 20, "bold"),
    )
    style.configure(
        "CardLabel.TLabel",
        background=SURFACE,
        foreground=MUTED,
        font=(family, 9),
    )

    style.configure(
        "TEntry",
        padding=(10, 8),
        fieldbackground=SURFACE,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
    )
    style.configure(
        "Accent.TButton",
        padding=(14, 9),
        background=ACCENT,
        foreground="#ffffff",
        borderwidth=0,
        focusthickness=0,
        font=(family, 10, "bold"),
    )
    style.map(
        "Accent.TButton",
        background=[("pressed", ACCENT_ACTIVE), ("active", ACCENT_ACTIVE)],
        foreground=[("disabled", "#d7deed")],
    )
    style.configure(
        "Sidebar.TButton",
        padding=(16, 10),
        anchor="w",
        background=SIDEBAR,
        foreground="#d7deea",
        borderwidth=0,
        focusthickness=0,
        font=(family, 10),
    )
    style.map(
        "Sidebar.TButton",
        background=[("active", SIDEBAR_HOVER)],
        foreground=[("active", "#ffffff")],
    )
    style.configure(
        "SidebarSelected.TButton",
        padding=(16, 10),
        anchor="w",
        background=SIDEBAR_SELECTED,
        foreground="#ffffff",
        borderwidth=0,
        focusthickness=0,
        font=(family, 10, "bold"),
    )
    style.map(
        "SidebarSelected.TButton",
        background=[("active", SIDEBAR_SELECTED)],
    )
    style.configure("TSeparator", background=BORDER)
    return style


def _preferred_font(root: tk.Misc) -> str:
    families = set(tkfont.families(root))
    for candidate in (
        "Microsoft YaHei UI",
        "PingFang SC",
        "Noto Sans CJK SC",
        "Segoe UI",
        "Arial",
    ):
        if candidate in families:
            return candidate
    return tkfont.nametofont("TkDefaultFont").cget("family")
