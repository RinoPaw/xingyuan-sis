"""Measure real Tk page-switch costs using a disposable demo database.

Run on the affected Windows machine:
    uv run python tools/profile_gui_navigation.py

The script does not read or modify the user's normal SIS database or session.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import nullcontext
import cProfile
import os
from pathlib import Path
import pstats
import tempfile
from time import perf_counter
from unittest.mock import patch
import tkinter as tk


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile actual Tk page-switch costs")
    parser.add_argument("--trace", choices=("overview", "students", "academics", "courses",
                        "grades", "announcements", "data"), help="Trace Python/Tk callbacks on the second visit to this page")
    args = parser.parse_args()
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

                callback_times = defaultdict(lambda: [0, 0.0])
                collecting = [False]
                original_callback = tk.CallWrapper.__call__

                def timed_callback(wrapper, *values):
                    if not collecting[0]:
                        return original_callback(wrapper, *values)
                    function = wrapper.func
                    code = getattr(function, "__code__", None)
                    if code is None:
                        method = getattr(function, "__func__", None)
                        code = getattr(method, "__code__", None)
                    label = (f"{Path(code.co_filename).name}:{code.co_firstlineno} "
                             f"{getattr(function, '__qualname__', type(function).__name__)}") if code else repr(function)
                    begin = perf_counter()
                    try:
                        return original_callback(wrapper, *values)
                    finally:
                        elapsed = (perf_counter() - begin) * 1000
                        callback_times[label][0] += 1
                        callback_times[label][1] += elapsed

                tracing = (patch.object(tk.CallWrapper, "__call__", timed_callback)
                           if args.trace else nullcontext())
                with tracing, patch.object(VectorCanvas, "render", timed_render), patch.object(
                    CampusController, "rows", timed_rows
                ):
                    window = MainWindow(root, db, Identity("Administrator", "admin"),
                                        on_logout=lambda: None)
                    window.pack(fill="both", expand=True)
                    root.update()
                    print(f"Tk {root.tk.call('info','patchlevel')} / "
                          f"SVG {getattr(root,'campus_svg_supported',False)} / "
                          f"Tk scaling {root.tk.call('tk', 'scaling')}")
                    print("阶段 | 页面 | 切页逻辑ms | 绘制及布局ms | "
                          "SVG调用/重建 | SVG累计ms | 数据查询ms")
                    for phase in ("首次", "重访"):
                        for key, title in window.navigation:
                            for name in stats:
                                stats[name] = 0 if name.endswith(("calls", "new")) else 0.0
                            detailed = args.trace == key and phase == "重访"
                            profile = cProfile.Profile() if detailed else None
                            if detailed:
                                callback_times.clear()
                                collecting[0] = True
                                profile.enable()
                            start = perf_counter()
                            window.show_page(key)
                            built = perf_counter()
                            if detailed:
                                root.update_idletasks()
                                idle_done = perf_counter()
                            root.update()
                            painted = perf_counter()
                            if detailed:
                                profile.disable()
                                collecting[0] = False
                            print(f"{phase} | {title} | {(built-start)*1000:8.1f} | "
                                  f"{(painted-built)*1000:10.1f} | "
                                  f"{stats['svg_calls']}/{stats['svg_new']} | "
                                  f"{stats['svg_ms']:8.1f} | {stats['data_ms']:8.1f}")
                            if detailed:
                                print(f"  Tk update_idletasks: {(idle_done-built)*1000:.1f} ms; "
                                      f"remaining update: {(painted-idle_done)*1000:.1f} ms; "
                                      f"compact: {getattr(window, 'compact_inspector', None)}")
                                print(f"  Python callbacks: {sum(x[0] for x in callback_times.values())}")
                                for label, (count, elapsed) in sorted(callback_times.items(),
                                        key=lambda item: item[1][1], reverse=True)[:18]:
                                    print(f"    {count:5d} calls / {elapsed:8.1f} ms  {label}")
                                print("  Python profile (top 22 by cumulative time):")
                                pstats.Stats(profile).strip_dirs().sort_stats("cumulative").print_stats(22)
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
