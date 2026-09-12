"""Native line input with an optional menu theme; scripts keep plain prompts."""
from contextlib import contextmanager
from contextvars import ContextVar
import os
import sys

_ACTIVE = ContextVar("menu_input_style", default=False)
_SURFACE = "\x1b[48;5;235m\x1b[38;5;252m"
_RESET = "\x1b[0m"
_ESCAPE_BINDING_READY = False


@contextmanager
def input_style(enabled: bool):
    token = _ACTIVE.set(enabled)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def _enable_escape_cancel() -> None:
    """Make Esc cancel GNU Readline input without replacing native line editing.

    Readline has no direct "return a cancelled input" action. Mapping Esc to
    Ctrl+U followed by Ctrl+D clears the current line and then raises EOFError,
    which read_input translates into the same cancellation path as Ctrl+C.
    The binding is installed once for the interactive process; unsupported
    readline implementations simply keep their normal behaviour.
    """
    global _ESCAPE_BINDING_READY
    if _ESCAPE_BINDING_READY or os.name == "nt":
        return
    try:
        import readline

        readline.parse_and_bind(r'"\e": "\C-u\C-d"')
    except (ImportError, AttributeError, ValueError):
        return
    _ESCAPE_BINDING_READY = True


def read_input(prompt: str) -> str:
    interactive = _ACTIVE.get() and sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        return input(prompt)

    _enable_escape_cancel()
    colored = os.environ.get("NO_COLOR") is None
    shown = f"{_SURFACE}\x1b[2K  {prompt}" if colored else prompt
    try:
        return input(shown)
    except EOFError as error:
        # In the interactive TUI, EOF is also the portable cancellation path
        # used by the Esc binding above.
        raise KeyboardInterrupt from error
    finally:
        if colored:
            sys.stdout.write(_RESET)
            sys.stdout.flush()


def heading(title: str) -> None:
    text = f"✦ 星原 / {title}"
    if _ACTIVE.get() and sys.stdout.isatty() and os.environ.get("NO_COLOR") is None:
        print(f"{_SURFACE}{text}{_RESET}\n")
    else:
        print(text + "\n")
