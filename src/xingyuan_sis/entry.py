from __future__ import annotations

from pathlib import Path
import sqlite3
import sys
from typing import Sequence

from .cli import build_parser, run as run_cli
from .database import initialize_database
from .terminal_capabilities import detect_terminal


_TKINTER_INSTALL_HINT = """无法启动 GUI：当前 Python 未安装 Tkinter/Tcl-Tk。
Tkinter 不是 PyPI 包，不能通过 `pip install tkinter` 安装。
Windows：重新运行 Python 安装程序，选择 Modify，并启用 “tcl/tk and IDLE”。
Linux：安装当前 Python 对应的 Tk 包（Debian/Ubuntu 通常为 python3-tk）。
检查：python -m tkinter"""


def _run_menu(db_path: Path | None, *, mode: str) -> int:
    initialize_database(db_path)
    capabilities = detect_terminal()
    if not capabilities.interactive:
        print("当前环境不是交互终端；请使用 xy <command>。", file=sys.stderr)
        return 2

    if mode == "basic" or (mode == "auto" and not capabilities.supports_tui):
        from .basic_ui import run
    else:
        from .tui.app import run

    run(db_path)
    return 0


def _run_gui(db_path: Path | None) -> int:
    initialize_database(db_path)
    try:
        from .gui.app import run
    except ImportError as error:
        if not _is_tkinter_import_error(error):
            raise
        print(_TKINTER_INSTALL_HINT, file=sys.stderr)
        return 1

    run(db_path)
    return 0


def _is_tkinter_import_error(error: ImportError) -> bool:
    name = getattr(error, "name", None)
    return name in {"tkinter", "_tkinter"} or "tkinter" in str(error).lower()


def main(argv: Sequence[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(raw)

    try:
        if args.group is None:
            if args.gui:
                return _run_gui(args.db)
            mode = "tui" if args.tui else "basic" if args.basic else "auto"
            return _run_menu(args.db, mode=mode)

        if args.group != "auth":
            from .auth_cli import authorize, require_identity

            initialize_database(args.db)
            identity = require_identity(args.db)
            authorize(identity, args)
        return run_cli(args, parser)
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130
    except EOFError:
        print("\n输入已结束，操作已取消。", file=sys.stderr)
        return 1
    except (ValueError, sqlite3.Error, OSError) as error:
        print(f"操作失败：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
