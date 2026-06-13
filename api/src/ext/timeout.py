import asyncio
import functools
from collections.abc import Callable, Coroutine
from datetime import timedelta
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def timeout(
    *,
    duration: timedelta,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
    def decorator(func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            async with asyncio.timeout(duration.total_seconds()):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
