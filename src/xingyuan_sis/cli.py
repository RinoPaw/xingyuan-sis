from __future__ import annotations

import argparse
import sqlite3
import sys
from typing import Sequence

from .cli_schema import build_parser
from .commands import print_table, run_group
from .database import initialize_database
from .service import XingyuanService


__all__ = ["build_parser", "main", "print_table", "run"]


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.group is None:
        parser.print_help()
        return 2
    if args.basic or args.tui:
        parser.error("--basic / --tui 不能与 CLI 子命令同时使用")

    initialize_database(args.db)
    if args.group == "auth":
        from .auth_cli import run as run_auth

        return run_auth(args.db, args)

    service = XingyuanService(args.db)
    return run_group(service, args)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args, parser)
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
    from .entry import main as entry_main

    raise SystemExit(entry_main())
