"""Single semantic palette for terminal surfaces, controls and line input. No I/O."""

_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"

# Text roles.
_TEXT_PRIMARY = "\x1b[38;5;252m"
_TEXT_SECONDARY = "\x1b[38;5;248m"
_TEXT_ACCENT = "\x1b[38;5;111m"
_TEXT_ON_SELECTED = _TEXT_PRIMARY
_TEXT_DANGER = "\x1b[38;5;217m"

# Structural roles.
_BORDER_SUBTLE = "\x1b[38;5;239m"
_SURFACE_DEFAULT = "\x1b[48;5;235m"
_SURFACE_TOPBAR = "\x1b[48;5;234m"
_SURFACE_FOOTER = "\x1b[48;5;236m"
_SURFACE_INTERACTIVE = "\x1b[48;5;237m"
_SURFACE_SELECTED = "\x1b[48;5;238m"

# Decoration is not an information state.
_DECORATIVE_GOLD = "\x1b[38;5;180m"
