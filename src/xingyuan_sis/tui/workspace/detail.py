from __future__ import annotations

from typing import Any

from .. import screen
from ..view_common import safe
from .data import COLLECTIONS, Catalog
from .inspector import Line, is_editing, expand_options, field_segment
from .state import Workspace


def lines(
    key: str, row: dict[str, Any], catalog: Catalog, state: Workspace | None = None,
) -> list[Line]:
    """One archive geometry for both browsing and editing each entity."""
    result: list[Line] = []
    title_key = "title" if key == "announcements" else "student_no" if key == "grades" else "name"
    ordered = sorted(COLLECTIONS[key].fields, key=lambda field: field.key != title_key)
    for field in ordered:
        style = screen._BOLD + screen._TEXT_PRIMARY if field.key == title_key else screen._TEXT_PRIMARY
        segment = field_segment(state, catalog, key, row, field.key, style=style)
        if key == "announcements" and field.key == "body":
            result.extend(([], [("正文", screen._BOLD + screen._TEXT_PRIMARY, "")]))
            for paragraph in str(row["body"]).splitlines():
                result.append([(safe(paragraph) if paragraph else "", screen._TEXT_PRIMARY, "")])
        elif field.key == title_key:
            result.append([segment])
        else:
            result.append([(field.label + "  ", screen._TEXT_SECONDARY, ""), segment])

    if key == "announcements":
        result.insert(2, [("发布于  " + safe(row["created_at"]), screen._TEXT_SECONDARY, "")])
    else:
        related_key, related = catalog.related(key, row)
        result.extend(([], [(f"关联{COLLECTIONS[related_key].noun}  {len(related):02d}",
                             screen._BOLD + screen._TEXT_PRIMARY, "")]))
        if not related:
            result.append([("暂无关联记录", screen._TEXT_SECONDARY, "")])
        for item in related:
            if related_key == "grades":
                score = safe(item["score"]) if item["score"] is not None else "待录入"
                label = f"{safe(item['student_name'])} · {safe(item['semester'])} · {score}"
            else:
                label = safe(item["name"])
            result.append([("↗ " + label, screen._TEXT_ACCENT + "\x1b[4m",
                            "" if is_editing(state) else f"related:{related_key}:{item['id']}")])
    return expand_options(result, state)
