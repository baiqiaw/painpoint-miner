"""指数退避重试工具。"""

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("painpoint_miner")

F = TypeVar("F", bound=Callable[..., Any])


def with_retry(
    max_attempts: int = 3,
    base_wait: float = 1.0,
    max_wait: float = 30.0,
    retry_on: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """指数退避重试装饰器。"""

    def decorator(func: F) -> F:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=base_wait, max=max_wait),
            retry=retry_if_exception_type(retry_on),
            before_sleep=lambda state: logger.warning(
                "Retrying %s (attempt %d/%d): %s",
                func.__name__,
                state.attempt_number,
                max_attempts,
                state.outcome.exception(),
            ),
        )
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
