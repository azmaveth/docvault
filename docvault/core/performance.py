"""
Performance monitoring and profiling utilities.
"""

import functools
import logging
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Global performance stats
_performance_stats: dict[str, dict[str, Any]] = {}


@contextmanager
def timer(operation_name: str) -> Generator[None, None, None]:
    """
    Context manager for timing operations.

    Usage:
        with timer("document_scraping"):
            # ... scraping code ...
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        record_timing(operation_name, duration)


def performance_monitor(operation_name: str | None = None):
    """
    Decorator for monitoring function performance.

    Usage:
        @performance_monitor("embedding_generation")
        async def generate_embeddings(text):
            # ... implementation ...
    """

    def decorator(func: Callable) -> Callable:
        name = operation_name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                record_timing(name, duration)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                record_timing(name, duration)

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def record_timing(operation: str, duration: float):
    """Record timing information for an operation."""
    if operation not in _performance_stats:
        _performance_stats[operation] = {
            "count": 0,
            "total_time": 0.0,
            "min_time": float("inf"),
            "max_time": 0.0,
            "avg_time": 0.0,
        }

    stats = _performance_stats[operation]
    stats["count"] += 1
    stats["total_time"] += duration
    stats["min_time"] = min(stats["min_time"], duration)
    stats["max_time"] = max(stats["max_time"], duration)
    stats["avg_time"] = stats["total_time"] / stats["count"]

    # Log slow operations
    if duration > 5.0:  # Log operations taking more than 5 seconds
        logger.warning(f"Slow operation detected: {operation} took {duration:.2f}s")


def get_performance_stats() -> dict[str, dict[str, Any]]:
    """Get all recorded performance statistics."""
    return _performance_stats.copy()


def reset_performance_stats():
    """Reset all performance statistics."""
    global _performance_stats
    _performance_stats.clear()
    logger.info("Performance statistics reset")


def log_performance_summary():
    """Log a summary of performance statistics."""
    if not _performance_stats:
        logger.info("No performance statistics available")
        return

    logger.info("=== Performance Summary ===")
    for operation, stats in _performance_stats.items():
        logger.info(
            f"{operation}: {stats['count']} calls, "
            f"avg: {stats['avg_time']:.3f}s, "
            f"min: {stats['min_time']:.3f}s, "
            f"max: {stats['max_time']:.3f}s, "
            f"total: {stats['total_time']:.3f}s"
        )


class PerformanceProfiler:
    """
    Detailed performance profiler for complex operations.
    """

    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.checkpoints = []
        self.memory_usage = []

    def start(self):
        """Start profiling."""
        self.start_time = time.time()
        self.checkpoints = []
        self.memory_usage = []
        logger.debug(f"Started profiling: {self.name}")

    def checkpoint(self, label: str):
        """Record a checkpoint."""
        if self.start_time is None:
            raise RuntimeError("Profiler not started")

        current_time = time.time()
        elapsed = current_time - self.start_time

        # Get memory usage if psutil is available
        memory_mb = 0
        try:
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
        except ImportError:
            pass

        self.checkpoints.append(
            {"label": label, "elapsed_time": elapsed, "memory_mb": memory_mb}
        )

        logger.debug(f"Checkpoint '{label}': {elapsed:.3f}s, {memory_mb:.1f}MB")

    def finish(self):
        """Finish profiling and log results."""
        if self.start_time is None:
            raise RuntimeError("Profiler not started")

        total_time = time.time() - self.start_time

        logger.info(f"=== Profile Results: {self.name} ===")
        logger.info(f"Total time: {total_time:.3f}s")

        for i, checkpoint in enumerate(self.checkpoints):
            if i == 0:
                step_time = checkpoint["elapsed_time"]
            else:
                step_time = (
                    checkpoint["elapsed_time"] - self.checkpoints[i - 1]["elapsed_time"]
                )

            logger.info(
                f"  {checkpoint['label']}: "
                f"+{step_time:.3f}s "
                f"(total: {checkpoint['elapsed_time']:.3f}s, "
                f"mem: {checkpoint['memory_mb']:.1f}MB)"
            )

        # Record overall timing
        record_timing(f"profile.{self.name}", total_time)


@contextmanager
def profiler(name: str) -> Generator[PerformanceProfiler, None, None]:
    """
    Context manager for detailed profiling.

    Usage:
        with profiler("document_processing") as p:
            p.checkpoint("parsing")
            # ... parsing code ...
            p.checkpoint("extraction")
            # ... extraction code ...
    """
    prof = PerformanceProfiler(name)
    prof.start()
    try:
        yield prof
    finally:
        prof.finish()


class BatchProcessor:
    """
    Generic batch processor for optimizing operations.
    """

    def __init__(self, batch_size: int = 100, max_wait_time: float = 1.0):
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time
        self.pending_items = []
        self.last_flush_time = time.time()

    async def add_item(self, item: Any, processor_func: Callable):
        """Add an item to the batch."""
        self.pending_items.append((item, processor_func))

        # Flush if batch is full or max wait time exceeded
        current_time = time.time()
        if (
            len(self.pending_items) >= self.batch_size
            or current_time - self.last_flush_time >= self.max_wait_time
        ):
            await self.flush()

    async def flush(self):
        """Process all pending items."""
        if not self.pending_items:
            return

        logger.debug(f"Processing batch of {len(self.pending_items)} items")

        # Group items by processor function
        grouped_items = {}
        for item, func in self.pending_items:
            if func not in grouped_items:
                grouped_items[func] = []
            grouped_items[func].append(item)

        # Process each group
        for func, items in grouped_items.items():
            try:
                await func(items)
            except Exception as e:
                logger.error(f"Batch processing failed: {e}")

        self.pending_items.clear()
        self.last_flush_time = time.time()

    async def close(self):
        """Flush any remaining items and close."""
        await self.flush()


def memory_usage() -> float:
    """Get current memory usage in MB."""
    try:
        import psutil

        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return 0.0


def log_system_stats():
    """Log current system resource usage."""
    try:
        import psutil

        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)

        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_gb = memory.available / 1024 / 1024 / 1024

        # Disk usage for database directory
        import os

        from docvault import config

        db_dir = os.path.dirname(config.DB_PATH)
        disk = psutil.disk_usage(db_dir)
        disk_free_gb = disk.free / 1024 / 1024 / 1024

        logger.info(
            f"System stats: CPU {cpu_percent}%, "
            f"Memory {memory_percent}% ({memory_available_gb:.1f}GB free), "
            f"Disk {disk_free_gb:.1f}GB free"
        )

    except ImportError:
        logger.warning("psutil not available, cannot log system stats")
    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
