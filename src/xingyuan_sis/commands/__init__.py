"""Domain command runners for the xingyuan-sis CLI."""

from .common import print_table
from .dispatcher import run_group

__all__ = ["print_table", "run_group"]
