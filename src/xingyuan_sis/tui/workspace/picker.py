"""Shared option-picker state and presentation rules."""
from __future__ import annotations

from .state import FieldSession


PICKER_GUTTER = 2


def prepare_candidates(session: FieldSession) -> list[tuple[object, str]] | None:
    """Expose only values that would actually change the active field.

    The field itself keeps displaying the current value while the picker expands
    underneath it.  Removing that value from ``session.options`` also keeps
    keyboard/mouse indices identical to the visible candidate list.
    """
    if session.options is None:
        return None

    current = session.values.get(session.active_key)
    if any(value == current for value, _ in session.options):
        session.options = [
            option for option in session.options
            if option[0] != current
        ]
        session.option_index = 0
    elif session.options:
        session.option_index = min(max(0, session.option_index), len(session.options) - 1)
    else:
        session.option_index = 0
    return session.options
