"""Normalize composite values only when their available domain changes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping


@dataclass(frozen=True)
class Dependency:
    field: str
    policy: str  # "clear" for selection changes, "clamp" for numeric bounds


# Domain dependencies belong to the data model, not to input-event branches.
# Unrelated fields (for example element and affinity) have no dependency edge.
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
}

Domain = Callable[[str, Mapping[str, Any]], list[tuple[Any, str]] | None]


def has_dependents(collection: str, field: str) -> bool:
    return (collection, field) in _RULES


def clamp_to_domain(value: Any, domain: list[tuple[Any, str]] | None) -> Any:
    """Constrain a *confirmed* numeric value to the nearest allowed number."""
    if value is None:
        return None
    allowed = [choice for choice, _ in domain or () if type(choice) is int]
    if not allowed:
        return value
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return value
    if numeric in allowed:
        return numeric
    return min(allowed, key=lambda choice: (abs(choice - numeric), choice))


def reconcile(
    collection: str,
    before: Mapping[str, Any],
    values: MutableMapping[str, Any],
    options_for: Domain,
) -> set[str]:
    """Recheck a child only if a changed parent actually changes its domain.

    Compare possible *values*, not labels or parent identities. Thus changing
    an independent field triggers no normalization, and changing a parent
    whose child choices remain identical leaves that child untouched.
    """
    changed: set[str] = set()
    # A normalized intermediate field can change domains farther downstream.
    for _ in range(1 + len(_RULES)):
        progress = False
        for (owner, parent), dependencies in _RULES.items():
            if owner != collection or before.get(parent) == values.get(parent):
                continue
            for dependency in dependencies:
                old_domain = options_for(dependency.field, before)
                new_domain = options_for(dependency.field, values)
                old_choices = {value for value, _ in old_domain or ()}
                new_choices = {value for value, _ in new_domain or ()}
                if old_choices == new_choices:
                    continue
                current = values.get(dependency.field)
                if current is None:
                    continue
                normalized = (
                    None if dependency.policy == "clear"
                    else clamp_to_domain(current, new_domain)
                )
                if current != normalized:
                    values[dependency.field] = normalized
                    changed.add(dependency.field)
                    progress = True
        if not progress:
            break
    return changed
