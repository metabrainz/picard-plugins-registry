"""Cross-platform terminal color support."""

import os
import sys


_enabled = True


def init(*, no_color: bool = False) -> None:
    """Initialize color support.

    Colors are disabled if:
    - no_color is True (--no-color flag)
    - NO_COLOR environment variable is set
    - stdout is not a TTY
    """
    global _enabled
    _enabled = not no_color and "NO_COLOR" not in os.environ and sys.stdout.isatty()

    # Enable ANSI colors on Windows
    if _enabled and sys.platform == "win32":
        os.system("")  # noqa: S605  # ty: ignore[deprecated]


def _wrap(code: str, text: str) -> str:
    if _enabled:
        return f"\033[{code}m{text}\033[0m"
    return text


def bold(text: str) -> str:
    return _wrap("1", text)


def dim(text: str) -> str:
    return _wrap("2", text)


def green(text: str) -> str:
    return _wrap("32", text)


def yellow(text: str) -> str:
    return _wrap("33", text)


def blue(text: str) -> str:
    return _wrap("34", text)


def cyan(text: str) -> str:
    return _wrap("36", text)


def red(text: str) -> str:
    return _wrap("31", text)
