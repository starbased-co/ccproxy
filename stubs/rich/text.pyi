"""Type stubs for rich.text."""

from typing import Any

class Text:
    """Rich Text type stub."""

    def __init__(self, text: str = "", **kwargs: Any) -> None: ...
    def append(self, text: str, *, style: str | None = None, **kwargs: Any) -> None: ...
