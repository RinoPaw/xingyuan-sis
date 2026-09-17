from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from ..view_common import safe
from .data import Catalog

if TYPE_CHECKING:
    from .state import Form


def project_record(
    row: Mapping[str, Any],
    form: Form | None = None,
) -> dict[str, Any]:
    """Return the single record projection consumed by inspector formatters.

    Existing-record editing may override only the fields owned by the current
    edit session. Formatters receive only the resulting values and therefore do
    not branch on browse/edit mode.
    """
    values = dict(row)
    if form is None or form.mode != "edit":
        return values

    for field in form.fields:
        values[field.key] = form.values.get(field.key)
    return values


def display_value(
    catalog: Catalog,
    collection: str,
    values: Mapping[str, Any],
    field_key: str,
) -> str:
    """Format one field through the same path in every inspector state."""
    value = values.get(field_key)
    options = catalog.options(collection, field_key, dict(values))
    if options is not None:
        return next((label for option, label in options if option == value), safe(value))
    return safe(value)
