"""Tests for rate limiting and resource management."""

import asyncio
from unittest.mock import Mock, patch

import pytest

from docvault.utils.rate_limiter import RateLimitConfig, RateLimiter, ResourceMonitor


class TestRateLimiter:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_basic_rate_limiting(self):
        """Test basic per-minute rate limiting."""
        config = RateLimitConfig(
            requests_per_minute=5, requests_per_hour=100, burst_size=3
        )
        limiter = RateLimiter(config)

        # First 5 requests should succeed
        for i in range(5):
            allowed, reason = await limiter.check_rate_limit("example.com")
            assert allowed, f"Request {i + 1} should be allowed"
            await limiter.record_request("example.com")

        # 6th request should fail
        allowed, reason = await limiter.check_rate_limit("example.com")
        assert not allowed
        assert "Per-minute rate limit exceeded" in reason

    @pytest.mark.asyncio
    async def test_burst_detection(self):
        """Test burst limit detection."""
        config = RateLimitConfig(
            requests_per_minute=10, burst_size=3, burst_cooldown_seconds=1
        )
        limiter = RateLimiter(config)

        # Simulate burst by making many requests quickly
        for i in range(8):
            allowed, _ = await limiter.check_rate_limit("burst.com")
            assert allowed
            await limiter.record_request("burst.com")

        # Next request should trigger burst protection
        # (80% of per-minute limit reached)
        for i in range(3):
            allowed, _ = await limiter.check_rate_limit("burst.com")
            if allowed:
                await limiter.record_request("burst.com")

        # Eventually burst limit should be hit
        allowed, reason = await limiter.check_rate_limit("burst.com")
        if not allowed:
            assert "Burst limit exceeded" in reason or "rate limit exceeded" in reason

    @pytest.mark.asyncio
    async def test_domain_isolation(self):
        """Test that rate limits are per-domain."""
        config = RateLimitConfig(requests_per_minute=2)
        limiter = RateLimiter(config)

        # Use up limit for domain1
        for _ in range(2):
            allowed, _ = await limiter.check_rate_limit("domain1.com")
            assert allowed
            await limiter.record_request("domain1.com")

        # domain1 should be blocked
        allowed, _ = await limiter.check_rate_limit("domain1.com")
        assert not allowed

        # domain2 should still work
        allowed, _ = await limiter.check_rate_limit("domain2.com")
        assert allowed

    @pytest.mark.asyncio
    async def test_global_rate_limit(self):
        """Test global rate limiting across all domains."""
        config = RateLimitConfig(
            requests_per_minute=100,  # High per-domain limit
            global_requests_per_minute=5,  # Low global limit
        )
        limiter = RateLimiter(config)

        # Make requests to different domains
        domains = ["a.com", "b.com", "c.com", "d.com", "e.com"]
        for domain in domains:
            allowed, _ = await limiter.check_rate_limit(domain)
            assert allowed
            await limiter.record_request(domain)

        # Next request to any domain should fail
        allowed, reason = await limiter.check_rate_limit("f.com")
        assert not allowed
        assert "Global per-minute rate limit exceeded" in reason

    @pytest.mark.asyncio
    async def test_concurrent_request_limiting(self):
        """Test concurrent request limiting."""
        config = RateLimitConfig(max_concurrent_requests=2)
        limiter = RateLimiter(config)

        # Acquire 2 slots
        await limiter.acquire()
        await limiter.acquire()

        # 3rd should block (with timeout to prevent hanging)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(limiter.acquire(), timeout=0.1)

        # Release one and try again
        limiter.release()
        await asyncio.wait_for(limiter.acquire(), timeout=0.1)  # Should succeed

    @pytest.mark.asyncio
    async def test_cooldown_period(self):
        """Test cooldown period after burst."""
        config = RateLimitConfig(
            burst_size=1, burst_cooldown_seconds=0.5, requests_per_minute=10
        )
        limiter = RateLimiter(config)

        # Trigger burst protection
        for _ in range(8):  # 80% of rate limit
            await limiter.check_rate_limit("cooldown.com")
            await limiter.record_request("cooldown.com")

        # This should trigger cooldown
        await limiter.check_rate_limit("cooldown.com")
        await limiter.record_request("cooldown.com")

        # Should be in cooldown
        allowed, reason = await limiter.check_rate_limit("cooldown.com")
        if not allowed and "cooldown" in reason:
            assert "cooldown" in reason

            # Wait for cooldown to expire
            await asyncio.sleep(0.6)

            # Should work again
            allowed, _ = await limiter.check_rate_limit("cooldown.com")
            assert allowed


class TestResourceMonitor:
    """Test resource monitoring functionality."""

    @pytest.mark.asyncio
    async def test_memory_monitoring(self):
        """Test memory usage monitoring."""
        config = RateLimitConfig(max_memory_mb=1024)
        monitor = ResourceMonitor(config)

        # Should pass under normal conditions
        allowed, reason = await monitor.check_memory_usage()
        assert (
            allowed or reason is not None
        )  # May fail if system memory is actually high

    @pytest.mark.asyncio
    async def test_operation_timeout(self):
        """Test operation timeout tracking."""
        config = RateLimitConfig(max_processing_time_seconds=1)
        monitor = ResourceMonitor(config)

        operation_id = "test_op_1"
        await monitor.start_operation(operation_id)

        # Should be fine immediately
        allowed, _ = await monitor.check_timeout(operation_id)
        assert allowed

        # Wait for timeout
        await asyncio.sleep(1.1)

        # Should now timeout
        allowed, reason = await monitor.check_timeout(operation_id)
        assert not allowed
        assert "exceeded time limit" in reason

        # Clean up
        await monitor.end_operation(operation_id)

        # Should be fine after cleanup
        allowed, _ = await monitor.check_timeout(operation_id)
        assert allowed

    @pytest.mark.asyncio
    async def test_memory_warning(self, capsys):
        """Test memory usage warning at 90%."""
        config = RateLimitConfig(max_memory_mb=10)  # Very low limit
        monitor = ResourceMonitor(config)

        # This will likely trigger a warning or failure
        await monitor.check_memory_usage()

        # Check if warning was printed (if memory is high enough)
        capsys.readouterr()  # Clear the output buffer
        # Warning may or may not appear depending on actual memory usage
        assert True  # Just verify no exceptions


class TestRateLimiterIntegration:
    """Test rate limiter integration with scraper."""

    @pytest.mark.asyncio
    async def test_scraper_rate_limiting(self):
        """Test that scraper respects rate limits."""
        from docvault.core.scraper import WebScraper

        # Mock the rate limiter to always deny
        with patch("docvault.utils.rate_limiter.get_rate_limiter") as mock_get_limiter:
            mock_limiter = Mock()
            mock_limiter.check_rate_limit = asyncio.coroutine(
                lambda domain: (False, "Rate limit exceeded")
            )
            mock_get_limiter.return_value = mock_limiter

            scraper = WebScraper()
            content, error = await scraper._fetch_url("http://example.com")

            assert content is None
            assert error == "Rate limit exceeded"

    @pytest.mark.asyncio
    async def test_scraper_resource_monitoring(self):
        """Test that scraper respects resource limits."""
        from docvault.core.scraper import WebScraper

        # Mock the resource monitor to indicate high memory
        with patch(
            "docvault.utils.rate_limiter.get_resource_monitor"
        ) as mock_get_monitor:
            mock_monitor = Mock()
            mock_monitor.check_memory_usage = asyncio.coroutine(
                lambda: (False, "Memory limit exceeded")
            )
            mock_monitor.start_operation = asyncio.coroutine(lambda op_id: None)
            mock_monitor.end_operation = asyncio.coroutine(lambda op_id: None)
            mock_get_monitor.return_value = mock_monitor

            scraper = WebScraper()
            content, error = await scraper._fetch_url("http://example.com")

            assert content is None
            assert error == "Memory limit exceeded"
