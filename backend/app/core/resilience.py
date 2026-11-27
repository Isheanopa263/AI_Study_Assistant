"""
Resilience and Fault Tolerance Module
Location: backend/app/core/resilience.py

Provides Circuit Breaker, Exponential Backoff, and Retry utilities for external AI services.
"""
import asyncio
import logging
import random
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, Type, Tuple

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """States of the Circuit Breaker state machine."""
    CLOSED = "CLOSED"        # Normal operational state; calls pass through.
    OPEN = "OPEN"            # Tripped state; calls fail immediately.
    HALF_OPEN = "HALF_OPEN"  # Testing state; allows a trial probe.


class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""
    def __init__(self, message: str = "Circuit breaker is OPEN. Upstream AI service unavailable."):
        super().__init__(message)


class CircuitBreaker:
    """Asynchronous Circuit Breaker protecting against cascading downstream failures."""

    def __init__(
        self,
        name: str = "GeminiCircuitBreaker",
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state: CircuitState = CircuitState.CLOSED
        self._consecutive_failures: int = 0
        self._last_state_change: float = time.time()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Calculates effective state accounting for recovery timeout expiration."""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_state_change >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        """Records a successful operation, resetting the breaker to CLOSED."""
        self._consecutive_failures = 0
        if self._state != CircuitState.CLOSED:
            logger.info(f"[{self.name}] Service recovered. State transitioning to CLOSED.")
            self._state = CircuitState.CLOSED
            self._last_state_change = time.time()

    def record_failure(self, error: Exception) -> None:
        """Records a failed operation, potentially tripping the circuit to OPEN."""
        self._consecutive_failures += 1
        logger.warning(
            f"[{self.name}] Failure recorded ({self._consecutive_failures}/{self.failure_threshold}): {error}"
        )

        if self._consecutive_failures >= self.failure_threshold:
            if self._state != CircuitState.OPEN:
                logger.error(
                    f"[{self.name}] Failure threshold reached. Tripping breaker to OPEN for {self.recovery_timeout}s."
                )
                self._state = CircuitState.OPEN
                self._last_state_change = time.time()

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Executes an async callable wrapped in circuit breaker protection."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            raise CircuitBreakerOpenException(
                f"[{self.name}] Circuit is OPEN. Fast-failing request."
            )

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure(exc)
            raise exc

    def get_status(self) -> Dict[str, Any]:
        """Returns metrics and operational metadata."""
        return {
            "name": self.name,
            "state": self.state.value,
            "consecutive_failures": self._consecutive_failures,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_seconds": self.recovery_timeout,
            "last_state_change_timestamp": self._last_state_change,
        }


async def retry_with_backoff(
    coroutine_func: Callable,
    retriable_exceptions: Tuple[Type[Exception], ...],
    max_retries: int = 3,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Executes an async function with exponential backoff retry logic.
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(1, max_retries + 1):
        try:
            return await coroutine_func(*args, **kwargs)
        except retriable_exceptions as exc:
            last_exception = exc
            if attempt == max_retries:
                logger.error(f"Retry exhausted after {attempt} attempts: {exc}")
                raise exc

            sleep_time = delay + (random.uniform(0, 0.1) if jitter else 0.0)
            logger.warning(
                f"Attempt {attempt} failed with {exc.__class__.__name__}. Retrying in {sleep_time:.2f}s..."
            )
            await asyncio.sleep(sleep_time)
            delay *= backoff_factor

    if last_exception:
        raise last_exception
    
ai_circuit_breaker = CircuitBreaker()