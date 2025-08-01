"""Generic singleton implementation for ccproxy."""

import threading
from typing import Any, TypeVar, cast

T = TypeVar("T")


def singleton(cls: type[T]) -> type[T]:
    """Thread-safe singleton decorator.

    This decorator ensures that only one instance of a class is created,
    with thread-safe initialization.

    Args:
        cls: The class to make a singleton

    Returns:
        The decorated class with singleton behavior

    Example:
        @singleton
        class MyConfig:
            def __init__(self):
                self.value = 42

        # Both will be the same instance
        config1 = MyConfig()
        config2 = MyConfig()
        assert config1 is config2
    """
    instances: dict[type[T], T] = {}
    lock = threading.Lock()

    class SingletonWrapper(cls):  # type: ignore[valid-type, misc]
        def __new__(cls: type[T], *args: Any, **kwargs: Any) -> T:  # type: ignore[misc]
            if cls not in instances:
                with lock:
                    # Double-check locking pattern
                    if cls not in instances:
                        instance = super().__new__(cls)  # type: ignore[misc]
                        instances[cls] = instance
            return instances[cls]

    SingletonWrapper.__name__ = cls.__name__
    SingletonWrapper.__qualname__ = cls.__qualname__
    SingletonWrapper.__module__ = cls.__module__
    SingletonWrapper.__doc__ = cls.__doc__

    return cast(type[T], SingletonWrapper)
