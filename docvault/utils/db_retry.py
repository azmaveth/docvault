"""Database retry utility for handling lock errors."""

import asyncio
import functools
import logging
import sqlite3
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_on_lock(max_attempts: int = 3, delay: float = 0.1, backoff: float = 2.0):
    """
    Decorator to retry database operations on lock errors.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e):
                        last_exception = e
                        if attempt < max_attempts - 1:
                            logger.debug(
                                f"Database locked on attempt {attempt + 1}/"
                                f"{max_attempts}, "
                                f"retrying in {current_delay:.2f}s..."
                            )
                            time.sleep(current_delay)
                            current_delay *= backoff
                        else:
                            logger.warning(
                                f"Database locked after {max_attempts} attempts"
                            )
                    else:
                        # Re-raise non-lock errors immediately
                        raise

            # If we get here, all attempts failed
            if last_exception:
                raise last_exception
            else:
                raise RuntimeError(f"Failed after {max_attempts} attempts")

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e):
                        last_exception = e
                        if attempt < max_attempts - 1:
                            logger.debug(
                                f"Database locked on attempt {attempt + 1}/"
                                f"{max_attempts}, "
                                f"retrying in {current_delay:.2f}s..."
                            )
                            await asyncio.sleep(current_delay)
                            current_delay *= backoff
                        else:
                            logger.warning(
                                f"Database locked after {max_attempts} attempts"
                            )
                    else:
                        # Re-raise non-lock errors immediately
                        raise

            # If we get here, all attempts failed
            if last_exception:
                raise last_exception
            else:
                raise RuntimeError(f"Failed after {max_attempts} attempts")

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def with_retry(func: Callable[..., T], *args, **kwargs) -> T:
    """
    Execute a function with retry logic for database locks.

    This is useful for one-off retries without decorating the function.
    """

    @retry_on_lock()
    def wrapped():
        return func(*args, **kwargs)

    return wrapped()


async def async_with_retry(func: Callable[..., T], *args, **kwargs) -> T:
    """
    Execute an async function with retry logic for database locks.

    This is useful for one-off retries without decorating the function.
    """

    @retry_on_lock()
    async def wrapped():
        return await func(*args, **kwargs)

    return await wrapped()
