from __future__ import annotations

import unicodedata
from typing import Iterable, Sequence

from ..terminal_input import read_input


UNCHANGED = object()


def display_width(value: object) -> int:
    return sum(
        2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        for char in str(value)
    )


def pad(value: object, width: int) -> str:
    text = str(value)
    return text + " " * max(0, width - display_width(text))


def print_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> None:
    rendered = [["—" if value is None or value == "" else str(value) for value in row] for row in rows]
    if not rendered:
        print("(无数据)")
        return
    widths = [
        max(display_width(headers[index]), *(display_width(row[index]) for row in rendered))
        for index in range(len(headers))
    ]
    print("  ".join(pad(header, widths[index]) for index, header in enumerate(headers)))
    for row in rendered:
        print("  ".join(pad(value, widths[index]) for index, value in enumerate(row)))


def print_fields(fields: Sequence[tuple[str, object]]) -> None:
    width = max((display_width(label) for label, _ in fields), default=0)
    for label, value in fields:
        shown = "—" if value is None or value == "" else value
        print(f"{pad(label, width)}  {shown}")


def prompt(label: str, value: str | None = None, *, required: bool = False) -> str | None:
    if value is not None:
        return value
    while True:
        text = read_input(f"{label}: ").strip()
        if text or not required:
            return text or None
        print(f"{label}不能为空。")


def prompt_int(label: str, value: int | None = None, *, required: bool = False) -> int | None:
    if value is not None:
        return value
    while True:
        text = read_input(f"{label}: ").strip()
        if not text and not required:
            return None
        try:
            return int(text)
        except ValueError:
            print("请输入整数。")


def prompt_float(label: str, value: float | None = None, *, required: bool = False) -> float | None:
    if value is not None:
        return value
    while True:
        text = read_input(f"{label}: ").strip()
        if not text and not required:
            return None
        try:
            return float(text)
        except ValueError:
            print("请输入数字。")


def edit_prompt(label: str, current: object, *, clearable: bool = False) -> object:
    shown = "—" if current is None or current == "" else current
    suffix = "；输入 - 清空" if clearable else ""
    raw = read_input(f"{label} [{shown}]（留空保持{suffix}）: ").strip()
    if not raw:
        return UNCHANGED
    if clearable and raw == "-":
        return None
    return raw


def confirm(message: str, assume_yes: bool = False) -> bool:
    if assume_yes:
        return True
    return read_input(f"{message} [y/N] ").strip().lower() in {"y", "yes"}
