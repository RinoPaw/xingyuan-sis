"""Single palette for terminal surfaces, controls and line input. No I/O."""

_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"

# Semantic color tokens. Layout code should use these roles instead of
# inventing component-local ANSI colors.
_TEXT_PRIMARY = "\x1b[38;5;252m"
_TEXT_SECONDARY = "\x1b[38;5;248m"
_TEXT_ACCENT = "\x1b[38;5;111m"
_TEXT_ON_SELECTED = "\x1b[38;5;255m"
_BORDER_SUBTLE = "\x1b[38;5;239m"

_SURFACE_DEFAULT = "\x1b[48;5;235m"
_SURFACE_TOPBAR = "\x1b[48;5;234m"
_SURFACE_FOOTER = "\x1b[48;5;236m"
_SURFACE_INTERACTIVE = "\x1b[48;5;237m"
_SURFACE_SELECTED = "\x1b[48;5;238m"

_TEXT_DANGER = "\x1b[38;5;217m"

# Decoration is deliberately separate from semantic information colors.
_DECORATIVE_GOLD = "\x1b[38;5;180m"

# Compatibility aliases for animation and older helpers. New UI code should
# prefer the semantic tokens above.
_ACCENT = _TEXT_ACCENT
_DIM = _TEXT_SECONDARY
_SELECTED = _SURFACE_SELECTED + _TEXT_ON_SELECTED
_GOLD = _DECORATIVE_GOLD
_SURFACE = _SURFACE_DEFAULT + _TEXT_PRIMARY
