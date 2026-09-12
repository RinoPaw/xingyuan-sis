from __future__ import annotations

from typing import TYPE_CHECKING

from ..terminal_ui import _wrap_line
from . import screen
from .view_common import Board, safe
from .workspace_data import Catalog

if TYPE_CHECKING:
    from .workspace import Workspace


def render_dashboard(board: Board, state: Workspace, catalog: Catalog) -> None:
    width = board.width
    split = width // 2 if width >= 76 else width
    lines: list[tuple[str, str, str]] = []

    lines.append(("校园脉络 / 学生元素分布", screen._BOLD + screen._TEXT_PRIMARY, ""))
    distribution = catalog.distribution()
    maximum = max((count for _, count in distribution), default=1)
    for label, count in distribution:
        bar = "━" * max(1, round(count / maximum * max(1, split - 20)))
        text = (
            screen._ansi(f"{safe(label):<4}", screen._TEXT_SECONDARY)
            + " "
            + screen._ansi(bar, screen._TEXT_ACCENT)
            + " "
            + screen._ansi(str(count), screen._BOLD + screen._TEXT_ACCENT)
        )
        lines.append((text, "", "collection:students"))
    if not distribution:
        lines.extend([
            ("", "", ""),
            ("校园尚未建立第一份学生档案。", screen._TEXT_SECONDARY, ""),
            ("[ 导入学生 CSV ]", screen._TEXT_ACCENT, "import"),
            ("[ 体验演示校园 ]", screen._TEXT_ACCENT, "seed"),
        ])

    lines.extend([("", "", ""), ("班级 / 学生人数", screen._BOLD + screen._TEXT_PRIMARY, "")])
    for row in catalog.records["classes"]:
        text = (
            screen._ansi(safe(row["name"]), screen._TEXT_PRIMARY)
            + "  "
            + screen._ansi(str(row["enrolled"]), screen._BOLD + screen._TEXT_ACCENT)
            + screen._ansi(" 人", screen._TEXT_SECONDARY)
        )
        lines.append((text, "", f"related:classes:{row['id']}"))

    grades = catalog.records["grades"]
    scores = [r["score"] for r in grades if r["score"] is not None]
    right = [
        ("成绩进度", screen._BOLD + screen._TEXT_PRIMARY, ""),
        ("", "", ""),
        (
            screen._ansi("已录入 ", screen._TEXT_SECONDARY)
            + screen._ansi(f"{len(scores)} / {len(grades)}", screen._BOLD + screen._TEXT_ACCENT),
            "",
            "collection:grades",
        ),
    ]
    for label, low, high in (
        ("90–100", 90, 101),
        ("80–89", 80, 90),
        ("60–79", 60, 80),
        ("60 以下", 0, 60),
    ):
        count = sum(low <= score < high for score in scores)
        right.append((
            screen._ansi(label, screen._TEXT_SECONDARY)
            + "  "
            + screen._ansi(str(count), screen._TEXT_PRIMARY),
            "",
            "collection:grades",
        ))

    right.extend([("", "", ""), ("导入记录", screen._BOLD + screen._TEXT_PRIMARY, "")])
    report_width = max(2, width - split - 3 if width >= 76 else width - 2)
    report_lines = state.report or ["本次还没有导入错误。"]
    report_style = screen._TEXT_PRIMARY if state.report else screen._TEXT_SECONDARY
    right.extend(
        (part, report_style, "")
        for line in report_lines
        for part in _wrap_line(safe(line), report_width)
    )

    if width < 76:
        lines.extend([("", "", ""), *right])
        panels = [(1, width - 2, lines)]
    else:
        panels = [(1, split - 3, lines), (split + 2, width - split - 3, right)]

    capacity = max(1, board.height - 11)
    state.detail_scroll = min(
        state.detail_scroll,
        max(0, max(len(panel[2]) for panel in panels) - capacity),
    )
    for x, panel_width, content in panels:
        for index, (text, style, action) in enumerate(
            content[state.detail_scroll:state.detail_scroll + capacity]
        ):
            board.put(x, 9 + index, text, style, action, panel_width)
