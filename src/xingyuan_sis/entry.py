from __future__ import annotations

from pathlib import Path
import sqlite3
import sys
from typing import Sequence

from .cli import build_parser, run as run_cli
from .database import initialize_database
from .terminal_capabilities import detect_terminal


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
    from .gui.app import run

    run(db_path)
    return 0


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
