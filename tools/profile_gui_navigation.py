"""Measure real Tk page-switch costs using a disposable demo database.

Run on the affected Windows machine:
    uv run python tools/profile_gui_navigation.py

The script does not read or modify the user's normal SIS database or session.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
from time import perf_counter
from unittest.mock import patch


def main() -> None:
    from tkinter import Tk
    from xingyuan_sis.auth import Identity
    from xingyuan_sis.database import initialize_database
    from xingyuan_sis.service import XingyuanService
    from xingyuan_sis.gui.controller import CampusController
    from xingyuan_sis.gui.main_window import MainWindow
    from xingyuan_sis.gui.theme import configure_styles
    from xingyuan_sis.gui.vector import VectorCanvas

    with tempfile.TemporaryDirectory(prefix="xy-gui-profile-") as temp:
        path = Path(temp)
        old_home = os.environ.get("XINGYUAN_HOME")
        os.environ["XINGYUAN_HOME"] = str(path / "auth")
        try:
            db = path / "demo.sqlite"
            initialize_database(db)
            XingyuanService(db).seed_demo()
            root = Tk()
            try:
                root.geometry("1280x820")
                configure_styles(root)
                root.update()
                stats = {"svg_ms": 0.0, "svg_calls": 0, "svg_new": 0,
                         "data_ms": 0.0, "data_calls": 0}
                original_render = VectorCanvas.render
                original_rows = CampusController.rows

                def timed_render(canvas):
                    previous = canvas.image
                    start = perf_counter()
                    try:
                        return original_render(canvas)
                    finally:
                        stats["svg_ms"] += (perf_counter() - start) * 1000
                        stats["svg_calls"] += 1
                        if canvas.image is not previous:
                            stats["svg_new"] += 1

                def timed_rows(controller, *args, **kwargs):
                    start = perf_counter()
                    try:
                        return original_rows(controller, *args, **kwargs)
                    finally:
                        stats["data_ms"] += (perf_counter() - start) * 1000
                        stats["data_calls"] += 1

                with patch.object(VectorCanvas, "render", timed_render), patch.object(
                    CampusController, "rows", timed_rows
                ):
                    window = MainWindow(root, db, Identity("Administrator", "admin"),
                                        on_logout=lambda: None)
                    window.pack(fill="both", expand=True)
                    root.update()
                    print(f"Tk {root.tk.call('info','patchlevel')} / "
                          f"SVG {getattr(root,'campus_svg_supported',False)}")
                    print("阶段 | 页面 | 切页逻辑ms | 绘制及布局ms | "
                          "SVG调用/重建 | SVG累计ms | 数据查询ms")
                    for phase in ("首次", "重访"):
                        for key, title in window.navigation:
                            for name in stats:
                                stats[name] = 0 if name.endswith(("calls", "new")) else 0.0
                            start = perf_counter()
                            window.show_page(key)
                            built = perf_counter()
                            root.update()
                            painted = perf_counter()
                            print(f"{phase} | {title} | {(built-start)*1000:8.1f} | "
                                  f"{(painted-built)*1000:10.1f} | "
                                  f"{stats['svg_calls']}/{stats['svg_new']} | "
                                  f"{stats['svg_ms']:8.1f} | {stats['data_ms']:8.1f}")
                    window.destroy()
            finally:
                root.destroy()
        finally:
            if old_home is None:
                os.environ.pop("XINGYUAN_HOME", None)
            else:
                os.environ["XINGYUAN_HOME"] = old_home


if __name__ == "__main__":
    main()
