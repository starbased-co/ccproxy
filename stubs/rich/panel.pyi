"""Type stubs for rich.panel."""

from typing import Any

class Panel:
    """Rich Panel type stub."""

    def __init__(
        self,
        renderable: Any,
        *,
        border_style: str | None = None,
        padding: tuple[int, int] | int | None = None,
        **kwargs: Any,
    ) -> None: ...
