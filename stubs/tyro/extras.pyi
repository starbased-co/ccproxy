"""Type stubs for tyro.extras."""

from collections.abc import Callable
from typing import Any

class SubcommandApp:
    def __init__(self) -> None: ...
    def command(
        self,
        func: Callable[..., Any] | None = None,
        *,
        name: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...
    def cli(
        self,
        *,
        prog: str | None = None,
        description: str | None = None,
        args: list[str] | None = None,
    ) -> None: ...
