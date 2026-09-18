"""Shared command metadata and shortcut resolution for the TUI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Command:
    action: str
    label: str
    shortcut: str | None = None
    toolbar: bool = True

    @property
    def hint(self) -> str:
        if not self.shortcut:
            return self.label
        key = self.shortcut.upper() if self.shortcut.isalpha() else self.shortcut
        return f"{key} {self.label}"


def resolve_shortcut(key: object, commands: Iterable[Command]) -> object:
    """Resolve a literal printable key through the commands active in one context."""
    if not isinstance(key, str) or len(key) != 1:
        return key
    folded = key.casefold()
    for command in commands:
        if command.shortcut and command.shortcut.casefold() == folded:
            return command.action
    return key
