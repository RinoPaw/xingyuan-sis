"""Native line input with an optional menu theme; scripts keep plain prompts."""
from contextlib import contextmanager
from contextvars import ContextVar
import os
import sys

_ACTIVE = ContextVar("menu_input_style", default=False)
_SURFACE = "\x1b[48;5;235m\x1b[38;5;252m"
_RESET = "\x1b[0m"


@contextmanager
def input_style(enabled: bool):
    token = _ACTIVE.set(enabled)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def read_input(prompt: str) -> str:
    if not (_ACTIVE.get() and sys.stdin.isatty() and sys.stdout.isatty()
            and os.environ.get("NO_COLOR") is None):
        return input(prompt)
    try:
        return input(f"{_SURFACE}\x1b[2K  {prompt}")
    finally:
        sys.stdout.write(_RESET)
        sys.stdout.flush()


def heading(title: str) -> None:
    text = f"✦ 星原 / {title}"
    if _ACTIVE.get() and sys.stdout.isatty() and os.environ.get("NO_COLOR") is None:
        print(f"{_SURFACE}{text}{_RESET}\n")
    else:
        print(text + "\n")
