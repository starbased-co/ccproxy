"""Type stubs for tyro."""

from collections.abc import Callable
from typing import Any, Generic, TypeVar, overload

_T = TypeVar("_T")

@overload
def cli(
    f: type[_T],
    *,
    prog: str | None = None,
    description: str | None = None,
    args: list[str] | None = None,
    default: _T | None = None,
    console_outputs: bool = True,
) -> _T: ...
@overload
def cli(
    f: Callable[..., _T],
    *,
    prog: str | None = None,
    description: str | None = None,
    args: list[str] | None = None,
    console_outputs: bool = True,
) -> _T: ...

class Conf:
    @staticmethod
    def arg(
        *,
        name: str | None = None,
        help: str | None = None,
        metavar: str | None = None,
        constructor: Callable[..., Any] | None = None,
    ) -> Any: ...

    class Positional(Generic[_T]):
        pass

    class Fixed(Generic[_T]):
        pass

conf = Conf
