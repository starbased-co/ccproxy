"""Type stubs for rich library."""

from typing import Any, TextIO

def print(*args: Any, file: TextIO | None = None, **kwargs: Any) -> None: ...
