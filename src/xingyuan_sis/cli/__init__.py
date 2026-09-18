from __future__ import annotations

import argparse

from .common import print_table
from .dispatcher import run_group
from .parser import build_parser
from ..database import initialize_database
from ..service import XingyuanService


__all__ = ["build_parser", "print_table", "run"]


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.group is None:
        parser.print_help()
        return 2
    if args.basic or args.tui:
        parser.error("--basic / --tui 不能与 CLI 子命令同时使用")

    initialize_database(args.db)
    if args.group == "auth":
        from ..auth_cli import run as run_auth

        return run_auth(args.db, args)

    service = XingyuanService(args.db)
    return run_group(service, args)
