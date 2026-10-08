"""Dependent values in composite fields are normalized at input boundaries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping


@dataclass(frozen=True)
class Dependency:
    field: str
    policy: str  # "clear" or "clamp"


_RULES: dict[tuple[str, str], tuple[Dependency, ...]] = {
    ("students", "family"): (Dependency("branch", "clear"),),
    ("students", "major_code"): (Dependency("class_number", "clear"),),
    ("students", "dorm_area"): (
        Dependency("dorm_building", "clear"),
        Dependency("dorm_room", "clear"),
    ),
    ("students", "dorm_building"): (Dependency("dorm_room", "clear"),),
    ("students", "birth_year"): (Dependency("birth_day", "clamp"),),
    ("students", "birth_month"): (Dependency("birth_day", "clamp"),),
    ("students", "birth_day"): (Dependency("birth_day", "clamp"),),
}


def reconcile(
    collection: str,
    changed_field: str,
    previous: Any,
    values: MutableMapping[str, Any],
    options_for: Callable[[str, Mapping[str, Any]], list[tuple[Any, str]] | None],
) -> set[str]:
    """Clear obsolete child selections or clamp values into the new domain.

    Parent changes invalidate their child selection even if two parents happen
    to admit the same label. Numeric constraints preserve the nearest valid
    value instead of discarding it.
    """
    if previous == values.get(changed_field):
        return set()
    changed: set[str] = set()
    for dependency in _RULES.get((collection, changed_field), ()):
        old = values.get(dependency.field)
        if old is None:
            continue
        if dependency.policy == "clear":
            new: Any = None
        else:
            options = options_for(dependency.field, values)
            allowed = [value for value, _ in options or () if type(value) is int]
            if not allowed:
                continue
            try:
                numeric = int(old)
            except (TypeError, ValueError):
                new = None
            else:
                # A valid masked value such as "09" needs no rewrite just
                # because its underlying option domain was recomputed.
                new = old if numeric in allowed else min(
                    allowed, key=lambda value: (abs(value - numeric), value)
                )
        if new != old:
            values[dependency.field] = new
            changed.add(dependency.field)
    return changed
