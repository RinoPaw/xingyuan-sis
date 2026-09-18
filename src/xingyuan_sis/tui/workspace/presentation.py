from __future__ import annotations

from typing import Any, Mapping

from ..view_common import safe
from .data import Catalog
from .state import FieldSession


def project_record(
    row: Mapping[str, Any],
    session: FieldSession | None = None,
) -> dict[str, Any]:
    """Return the one record projection consumed by every inspector formatter."""
    values = dict(row)
    if session is None:
        return values
    for field in session.fields:
        values[field.key] = session.values.get(field.key)
    return values


def display_value(
    catalog: Catalog,
    collection: str,
    values: Mapping[str, Any],
    field_key: str,
) -> str:
    """Format one field without knowing whether a field session exists."""
    value = values.get(field_key)
    options = catalog.options(collection, field_key, dict(values))
    if options is not None:
        return next((label for option, label in options if option == value), safe(value))
    return safe(value)
