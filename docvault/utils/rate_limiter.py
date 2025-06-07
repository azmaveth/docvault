"""Rate limiting and resource management utilities."""

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    pass


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    # Per-domain rate limiting
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10

    # Global rate limiting
    global_requests_per_minute: int = 300
    global_requests_per_hour: int = 5000

    # Resource limits
    max_concurrent_requests: int = 10
    max_memory_mb: int = 1024
    max_processing_time_seconds: int = 300

    # Cooldown periods
    rate_limit_cooldown_seconds: int = 60
    burst_cooldown_seconds: int = 300


class RateLimiter:
    """Thread-safe rate limiter with domain-specific and global limits."""

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._domain_requests: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self._global_requests = deque(maxlen=10000)
        self._burst_tracker: dict[str, int] = defaultdict(int)
        self._cooldowns: dict[str, datetime] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

    async def wait_if_needed(self, domain: str) -> float | None:
        """
        Calculate wait time if rate limited.

        Returns:
            None if no wait needed, or wait time in seconds
        """
        async with self._lock:
            now = time.time()

            # Check cooldown first
            if domain in self._cooldowns and self._cooldowns[domain] > now:
                return self._cooldowns[domain] - now

            # Check burst
            if self._burst_tracker.get(domain, 0) >= self.config.burst_size:
                # Need to wait for burst window to reset
                domain_requests = self._domain_requests[domain]
                if domain_requests:
                    oldest_in_minute = now - 60
                    requests_in_minute = [
                        t for t in domain_requests if t > oldest_in_minute
                    ]
                    if requests_in_minute:
                        # Wait until the oldest request in the minute window expires
                        wait_time = 60 - (now - requests_in_minute[0]) + 1
                        return wait_time

            # Check per-minute rate
            minute_ago = now - 60
            recent_requests = sum(
                1 for req_time in self._domain_requests[domain] if req_time > minute_ago
            )
            if recent_requests >= self.config.requests_per_minute:
                # Find when we can make the next request
                domain_requests = list(self._domain_requests[domain])
                domain_requests.sort()
                # Find the oldest request in the last minute
                for req_time in domain_requests:
                    if req_time > minute_ago:
                        # Wait until this request is older than 1 minute
                        wait_time = 60 - (now - req_time) + 0.1
                        return wait_time

            return None

    async def check_rate_limit(self, domain: str) -> tuple[bool, str | None]:
        """Check if a request to the domain is allowed.

        Returns:
            (allowed, reason) - True if allowed, False with reason if not
        """
        async with self._lock:
            now = time.time()

            # Check cooldown
            if domain in self._cooldowns:
                cooldown_end = self._cooldowns[domain]
                if datetime.now() < cooldown_end:
                    remaining = (cooldown_end - datetime.now()).total_seconds()
                    return (
                        False,
                        f"Domain {domain} is in cooldown for {remaining:.0f} seconds",
                    )

            # Clean old requests
            self._clean_old_requests(domain, now)

            # Check burst limit
            if self._burst_tracker[domain] >= self.config.burst_size:
                self._cooldowns[domain] = datetime.now() + timedelta(
                    seconds=self.config.burst_cooldown_seconds
                )
                return False, f"Burst limit exceeded for {domain}"

            # Check domain-specific rate limits
            domain_requests = self._domain_requests[domain]

            # Per-minute check
            minute_ago = now - 60
            recent_requests = sum(
                1 for req_time in domain_requests if req_time > minute_ago
            )
            if recent_requests >= self.config.requests_per_minute:
                return False, f"Per-minute rate limit exceeded for {domain}"

            # Per-hour check
            hour_ago = now - 3600
            hourly_requests = sum(
                1 for req_time in domain_requests if req_time > hour_ago
            )
            if hourly_requests >= self.config.requests_per_hour:
                return False, f"Per-hour rate limit exceeded for {domain}"

            # Check global rate limits
            global_minute_requests = sum(
                1 for req_time in self._global_requests if req_time > minute_ago
            )
            if global_minute_requests >= self.config.global_requests_per_minute:
                return False, "Global per-minute rate limit exceeded"

            global_hourly_requests = sum(
                1 for req_time in self._global_requests if req_time > hour_ago
            )
            if global_hourly_requests >= self.config.global_requests_per_hour:
                return False, "Global per-hour rate limit exceeded"

            return True, None

    async def record_request(self, domain: str):
        """Record a request for rate limiting."""
        async with self._lock:
            now = time.time()
            self._domain_requests[domain].append(now)
            self._global_requests.append(now)

            # Update burst tracker
            minute_ago = now - 60
            recent_count = sum(
                1 for req_time in self._domain_requests[domain] if req_time > minute_ago
            )
            if recent_count > self.config.requests_per_minute * 0.8:
                self._burst_tracker[domain] += 1
            else:
                self._burst_tracker[domain] = 0

    def _clean_old_requests(self, domain: str, now: float):
        """Remove requests older than 1 hour."""
        hour_ago = now - 3600

        # Clean domain requests
        domain_requests = self._domain_requests[domain]
        while domain_requests and domain_requests[0] < hour_ago:
            domain_requests.popleft()

        # Clean global requests
        while self._global_requests and self._global_requests[0] < hour_ago:
            self._global_requests.popleft()

    async def acquire(self):
        """Acquire a slot for concurrent request processing."""
        return await self._semaphore.acquire()

    def release(self):
        """Release a concurrent request slot."""
        self._semaphore.release()

    async def __aenter__(self):
        """Context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()


class ResourceMonitor:
    """Monitor and enforce resource usage limits."""

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._start_times: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def check_memory_usage(self) -> tuple[bool, str | None]:
        """Check if memory usage is within limits."""
        try:
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024

            if memory_mb > self.config.max_memory_mb:
                return (
                    False,
                    f"Memory usage ({memory_mb:.1f}MB) exceeds limit ({self.config.max_memory_mb}MB)",
                )

            # Warn if approaching limit
            if memory_mb > self.config.max_memory_mb * 0.9:
                print(f"Warning: Memory usage at {memory_mb:.1f}MB (90% of limit)")

            return True, None
        except ImportError:
            # psutil not available, skip check
            return True, None

    async def start_operation(self, operation_id: str):
        """Record start of an operation for timeout tracking."""
        async with self._lock:
            self._start_times[operation_id] = time.time()

    async def check_timeout(self, operation_id: str) -> tuple[bool, str | None]:
        """Check if an operation has exceeded time limit."""
        async with self._lock:
            if operation_id not in self._start_times:
                return True, None

            elapsed = time.time() - self._start_times[operation_id]
            if elapsed > self.config.max_processing_time_seconds:
                return (
                    False,
                    f"Operation exceeded time limit ({elapsed:.1f}s > {self.config.max_processing_time_seconds}s)",
                )

            return True, None

    async def end_operation(self, operation_id: str):
        """Mark end of an operation."""
        async with self._lock:
            self._start_times.pop(operation_id, None)


# Global instances
_rate_limiter: RateLimiter | None = None
_resource_monitor: ResourceMonitor | None = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        # Load config from environment
        from docvault import config as dv_config

        rate_config = RateLimitConfig(
            requests_per_minute=int(getattr(dv_config, "RATE_LIMIT_PER_MINUTE", 60)),
            requests_per_hour=int(getattr(dv_config, "RATE_LIMIT_PER_HOUR", 1000)),
            burst_size=int(getattr(dv_config, "RATE_LIMIT_BURST_SIZE", 10)),
            global_requests_per_minute=int(
                getattr(dv_config, "GLOBAL_RATE_LIMIT_PER_MINUTE", 300)
            ),
            global_requests_per_hour=int(
                getattr(dv_config, "GLOBAL_RATE_LIMIT_PER_HOUR", 5000)
            ),
            max_concurrent_requests=int(
                getattr(dv_config, "MAX_CONCURRENT_REQUESTS", 10)
            ),
            max_memory_mb=int(getattr(dv_config, "MAX_MEMORY_MB", 1024)),
            max_processing_time_seconds=int(
                getattr(dv_config, "MAX_PROCESSING_TIME_SECONDS", 300)
            ),
        )
        _rate_limiter = RateLimiter(rate_config)
    return _rate_limiter


def get_resource_monitor() -> ResourceMonitor:
    """Get or create the global resource monitor."""
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
    return _resource_monitor
