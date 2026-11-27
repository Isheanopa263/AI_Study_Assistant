"""
Unit and Integration Tests for AI Service Resilience, Circuit Breakers, and Retries.
Location: backend/tests/test_resilience.py
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient

from app.core.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenException,
    CircuitState,
    retry_with_backoff,
)


@pytest.mark.asyncio
async def test_circuit_breaker_normal_closed_state():
    """Verify circuit breaker executes functions normally in CLOSED state."""
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0)
    mock_func = AsyncMock(return_value="success_result")

    result = await breaker.call(mock_func, "arg1")
    assert result == "success_result"
    assert breaker.state == CircuitState.CLOSED
    assert breaker._consecutive_failures == 0


@pytest.mark.asyncio
async def test_circuit_breaker_trips_to_open_after_threshold_failures():
    """Verify circuit breaker trips to OPEN upon hitting failure threshold."""
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.2)
    mock_func = AsyncMock(side_effect=RuntimeError("Transient upstream outage"))

    # First failure
    with pytest.raises(RuntimeError):
        await breaker.call(mock_func)
    assert breaker.state == CircuitState.CLOSED
    assert breaker._consecutive_failures == 1

    # Second failure triggers trip
    with pytest.raises(RuntimeError):
        await breaker.call(mock_func)
    assert breaker.state == CircuitState.OPEN
    assert breaker._consecutive_failures == 2

    # Subsequent call must fast-fail without calling mock_func
    mock_func.reset_mock()
    with pytest.raises(CircuitBreakerOpenException):
        await breaker.call(mock_func)
    assert mock_func.call_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_recovers_to_half_open_and_closed():
    """Verify circuit breaker transitions to HALF_OPEN after timeout and recovers to CLOSED."""
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
    failing_func = AsyncMock(side_effect=RuntimeError("Failure"))

    with pytest.raises(RuntimeError):
        await breaker.call(failing_func)
    assert breaker.state == CircuitState.OPEN

    # Await recovery timeout window
    await asyncio.sleep(0.15)
    assert breaker.state == CircuitState.HALF_OPEN

    # Successful call resets circuit to CLOSED
    success_func = AsyncMock(return_value="recovered")
    result = await breaker.call(success_func)
    assert result == "recovered"
    assert breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_retry_with_backoff_succeeds_on_transient_failure():
    """Verify retry_with_backoff retries on designated exceptions and returns output."""
    attempts = 0

    async def flaky_operation():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ConnectionResetError("Transient network reset")
        return "recovered_data"

    res = await retry_with_backoff(
        coroutine_func=flaky_operation,
        retriable_exceptions=(ConnectionResetError,),
        max_retries=3,
        initial_delay=0.01,
        backoff_factor=1.5,
        jitter=False,
    )
    assert res == "recovered_data"
    assert attempts == 2


@pytest.mark.asyncio
async def test_resilience_status_endpoint(client: AsyncClient):
    """Integration test: validates GET /api/chat/resilience/status returns circuit metrics."""
    res = await client.get("/api/chat/resilience/status")
    assert res.status_code == 200
    data = res.json()
    assert "primary_model" in data
    assert "fallback_model" in data
    assert "circuit_breaker" in data
    assert data["circuit_breaker"]["state"] in ["CLOSED", "OPEN", "HALF_OPEN"]
    assert "failure_threshold" in data["circuit_breaker"]