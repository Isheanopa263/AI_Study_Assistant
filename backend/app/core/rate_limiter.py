import asyncio
import logging
import time
from collections import defaultdict
from typing import Dict, List

from fastapi import Depends, HTTPException, Request, status

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    In-memory rate limiter using a sliding window algorithm.

    Tracks request timestamps per user within a rolling time window.
    Uses asyncio.Lock to prevent race conditions when multiple
    concurrent requests from the same user arrive simultaneously.

    WARNING: This is an in-memory implementation for learning.
    In production, use Redis for distributed rate limiting across
    multiple server instances. We will cover that in Phase 10.

    How the sliding window works:
    - Each user has a list of request timestamps
    - On each request, timestamps older than the window are removed
    - If remaining count >= limit, the request is rejected
    - Otherwise, the current timestamp is added and request proceeds
    """

    def __init__(self, window_seconds: int = 60):
        """
        Initialize the rate limiter.

        Args:
            window_seconds: Size of the sliding window in seconds.
                           Default is 60 (one minute).
        """
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check_and_increment(
        self,
        user_id: str,
        limit_per_minute: int,
    ) -> bool:
        """
        Check if a user is within their rate limit and record the request.

        Uses asyncio.Lock to ensure thread safety when multiple
        concurrent requests from the same user modify the timestamp list.

        Args:
            user_id: The unique identifier of the user.
            limit_per_minute: Maximum allowed requests within the window.

        Returns:
            True if the request is allowed.
            False if the rate limit has been exceeded.
        """
        now = time.time()
        window_start = now - self.window_seconds

        # ---------------------------------------------------------
        # Acquire the lock
        # This prevents two concurrent requests from the same user
        # from reading and modifying the timestamp list simultaneously.
        # Without this, a race condition could allow extra requests
        # through the limit.
        # ---------------------------------------------------------
        async with self._lock:
            # Remove timestamps outside the current window
            self._requests[user_id] = [
                timestamp
                for timestamp in self._requests[user_id]
                if timestamp > window_start
            ]

            current_count = len(self._requests[user_id])

            if current_count >= limit_per_minute:
                logger.warning(
                    "Rate limit exceeded. user_id=%s count=%s limit=%s",
                    user_id,
                    current_count,
                    limit_per_minute,
                )
                return False

            # Record this request's timestamp
            self._requests[user_id].append(now)

            logger.debug(
                "Rate limit check passed. user_id=%s count=%s/%s",
                user_id,
                current_count + 1,
                limit_per_minute,
            )
            return True

    def get_remaining(self, user_id: str) -> int:
        """
        Returns the number of requests remaining in the current window.
        Used for informational purposes in response headers.
        """
        now = time.time()
        window_start = now - self.window_seconds
        active_requests = [
            t for t in self._requests.get(user_id, [])
            if t > window_start
        ]
        return max(0, len(active_requests))


# --------------------------------------------------------------------------
# GLOBAL RATE LIMITER INSTANCE
# --------------------------------------------------------------------------
# One instance shared across all requests.
# In production this would be replaced with a Redis-backed implementation.
# --------------------------------------------------------------------------

rate_limiter = RateLimiter(window_seconds=60)


# --------------------------------------------------------------------------
# DEPENDENCY
# --------------------------------------------------------------------------
# Usage in endpoint:
#   async def my_endpoint(
#       _: bool = Depends(check_rate_limit),
#       current_user: dict = Depends(get_current_user),
#   ):
# --------------------------------------------------------------------------

async def check_rate_limit(
    request: Request,
) -> bool:
    """
    FastAPI dependency that enforces rate limiting on endpoints.

    Extracts the user ID from the request state (set by auth dependency)
    and checks against the rate limiter.

    Raises 429 Too Many Requests if the limit is exceeded.

    Note: This dependency reads user_id from request.state because
    it runs before get_current_user in the dependency chain.
    In a real implementation, you would chain it after auth.
    For this exercise, we use a simplified approach.
    """
    # For this exercise, we use a simple header-based user identification.
    # In Phase 5, this will use the real JWT-decoded user_id.
    user_id = "stub-user-id"

    allowed = await rate_limiter.check_and_increment(
        user_id=user_id,
        limit_per_minute=10,
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait before sending another message.",
            headers={
                "Retry-After": "60",
                "X-RateLimit-Limit": "10",
                "X-RateLimit-Remaining": "0",
            },
        )

    return True