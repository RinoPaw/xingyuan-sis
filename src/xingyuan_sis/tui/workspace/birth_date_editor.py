"""User-facing composite editing for the canonical student birth_date field."""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any, Mapping

from ...schema import Field


BIRTH_DATE_FIELDS = (
    Field("birth_year", "年", kind="int", minimum=1, maximum=9999),
    Field("birth_month", "月", kind="int", minimum=1, maximum=12),
    Field("birth_day", "日", kind="int", minimum=1, maximum=31),
)
BIRTH_DATE_KEYS = tuple(field.key for field in BIRTH_DATE_FIELDS)


def parts(value: object | None) -> dict[str, int | None]:
    """Expand one canonical birth_date into the three transient editor values."""
    result: dict[str, int | None] = dict.fromkeys(BIRTH_DATE_KEYS)
    text = "" if value is None else str(value).strip()
    if not text:
        return result
    if len(text) == 4 and text.isdigit():
        result["birth_year"] = int(text)
        return result
    if len(text) == 7 and text.startswith("--"):
        try:
            month, day = int(text[2:4]), int(text[5:7])
            date(2000, month, day)
        except (ValueError, TypeError):
            return result
        result["birth_month"], result["birth_day"] = month, day
        return result
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return result
    result.update(
        birth_year=parsed.year,
        birth_month=parsed.month,
        birth_day=parsed.day,
    )
    return result


def canonical(values: Mapping[str, Any]) -> str | None:
    """Collapse a valid editor state back to the canonical storage representation."""
    year = values.get("birth_year")
    month = values.get("birth_month")
    day = values.get("birth_day")

    if year is None and month is None and day is None:
        return None
    if year is not None and month is None and day is None:
        if not 1 <= int(year) <= 9999:
            raise ValueError("出生年份应为 1～9999")
        return f"{int(year):04d}"
    if month is None or day is None:
        raise ValueError("出生日期可只填年份；填写月份时必须同时填写日期")

    check_year = 2000 if year is None else int(year)
    try:
        parsed = date(check_year, int(month), int(day))
    except ValueError:
        raise ValueError("出生日期不存在") from None
    if year is None:
        return f"--{parsed.month:02d}-{parsed.day:02d}"
    return parsed.isoformat()


def projected(values: Mapping[str, Any]) -> str | None:
    """Return a display projection while a group may still be incomplete."""
    try:
        return canonical(values)
    except (TypeError, ValueError):
        return None


def display(value: object | None) -> str:
    """Render known information without exposing the canonical ``--MM-DD`` syntax."""
    text = "" if value is None else str(value).strip()
    if not text:
        return "-"
    values = parts(text)
    year = values["birth_year"]
    month = values["birth_month"]
    day = values["birth_day"]
    if year is not None and month is None:
        return str(year)
    if year is None and month is not None and day is not None:
        return f"{month}-{day}"
    if year is not None and month is not None and day is not None:
        return f"{year}-{month}-{day}"
    return text


def options(field_key: str, values: Mapping[str, Any]) -> list[tuple[int | None, str]] | None:
    """Return dependent choices for month/day; year remains a small text slot."""
    if field_key == "birth_month":
        return [(None, "未指定")] + [(month, str(month)) for month in range(1, 13)]
    if field_key != "birth_day":
        return None

    month = values.get("birth_month")
    if month is None:
        return [(None, "未指定")]
    year = values.get("birth_year")
    check_year = 2000 if year is None else int(year)
    days = monthrange(check_year, int(month))[1]
    return [(day, str(day)) for day in range(1, days + 1)]
