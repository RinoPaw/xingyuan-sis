"""Commands available in record workspaces."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..commands import Command

if TYPE_CHECKING:
    from .data import Catalog


SEARCH = Command("search", "搜索", "/")
CREATE = Command("create", "增加", "a")
DELETE = Command("delete", "删除", "d", toolbar=False)
RESET_PASSWORD = Command("reset-password", "重置密码")
IMPORT = Command("import", "导入", "i")
EXPORT = Command("export", "导出", "o")
SEED = Command("seed", "演示", "g")
IMPORT_STUDENTS = Command("import", "导入学生 CSV", toolbar=False)
SEED_STUDENTS = Command("seed", "体验演示校园", toolbar=False)
FORM_SAVE = Command("save", "保存", "s", toolbar=False)


def available(catalog: Catalog, key: str) -> tuple[Command, ...]:
    """Return the commands actually available in the current workspace."""
    if catalog.read_only:
        return (SEARCH,)
    if key == "data":
        return (IMPORT, EXPORT, SEED)
    if key == "announcements":
        return (SEARCH, CREATE, DELETE)
    commands = (SEARCH, CREATE, DELETE)
    if key == "students":
        commands += (RESET_PASSWORD, IMPORT_STUDENTS, SEED_STUDENTS)
    return commands


def toolbar(catalog: Catalog, key: str) -> tuple[Command, ...]:
    return tuple(command for command in available(catalog, key) if command.toolbar)
