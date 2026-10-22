"""Font roles and process-private Windows font resources, without dependencies."""
from __future__ import annotations

import atexit
import ctypes
from functools import cache
from pathlib import Path
import sys
import tkinter as tk
from tkinter import font as tkfont


FONT_DIRECTORY = Path(__file__).with_name("assets") / "fonts"


@cache
def load_display_fonts() -> tuple[Path, ...]:
    """Load once per process. Other platforms retain installed-font fallbacks."""
    if sys.platform != "win32":
        return ()
    try:
        gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        add = gdi.AddFontResourceExW
        remove = gdi.RemoveFontResourceExW
        for call in (add, remove):
            call.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
            call.restype = ctypes.c_int
    except (AttributeError, OSError):
        return ()
    loaded = []
    for name in ("MFLiHei_Noncommercial-Regular.otf", "BarlowCondensed-Black.ttf"):
        path = FONT_DIRECTORY / name
        if path.is_file() and add(str(path), 0x10, None):  # FR_PRIVATE
            loaded.append(path)
    if loaded:
        def release():
            for path in reversed(loaded):
                remove(str(path), 0x10, None)
        atexit.register(release)
    return tuple(loaded)


def configure_fonts(root: tk.Misc) -> dict[str, str]:
    load_display_fonts()
    available = set(tkfont.families(root))
    default = tkfont.nametofont("TkDefaultFont", root=root).actual("family")

    def choose(*families):
        return next((family for family in families if family in available), default)

    body = choose("Source Han Sans SC", "Noto Sans SC", "Noto Sans CJK SC",
        "Microsoft YaHei UI", "PingFang SC", "Segoe UI", "Arial")
    root.campus_fonts = {
        "body": body,
        "display": choose("MFLiHeiNoncommercial", "造字工房力黑（非商用）",
            "Source Han Sans SC Heavy", "Noto Sans SC Black", body),
        "latin": choose("Tungsten Black", "Tungsten Bold", "Barlow Condensed Black",
            "Bahnschrift Condensed", "Arial Narrow", body),
    }
    return root.campus_fonts


def font_tuple(widget: tk.Misc, role: str, size: float, *, bold=False) -> tuple:
    root = widget
    while root.master is not None:
        root = root.master
    families = getattr(root, "campus_fonts", None) or configure_fonts(root)
    zoom = getattr(root, "campus_zoom", 1.0)
    # The supplied display faces already have their intended stroke weight.
    weight = "bold" if bold and role == "body" else "normal"
    return families[role], round(size * zoom), weight


def fitted_font(widget: tk.Misc, role: str, size: float, text: str, width: int) -> tuple:
    """Fit short graphic headings; data text is never compressed or rotated."""
    family, points, weight = font_tuple(widget, role, size)
    face = tkfont.Font(root=widget, family=family, size=points, weight=weight)
    measured = face.measure(text)
    if measured > width:
        points = max(12, int(points * max(1, width) / measured))
    return family, points, weight
