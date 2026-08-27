import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# ------------------------------------------------------------------------------
# Logger setup
# ------------------------------------------------------------------------------

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# REQUEST LOGGING AND TIMING MIDDLEWARE
# ------------------------------------------------------------------------------
# Runs for every single request.
# Assigns a unique request ID.
# Logs request start and completion.
# Measures processing time.
# Adds request ID to response headers for tracing.
# ------------------------------------------------------------------------------


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs every incoming request and its response.

    For each request:
    - Generates a unique request ID (UUID)
    - Stores it in request.state for access anywhere in the request lifecycle
    - Logs method, path, and start time
    - Measures total processing duration
    - Logs status code and duration on completion
    - Adds X-Request-ID header to response
    """

    async def dispatch(self, request: Request, call_next):
        # ------------------------------------------------------------------
        # Generate unique request ID
        # UUID4 is random and collision-resistant
        # This ID ties together all logs for a single request
        # ------------------------------------------------------------------
        request_id = str(uuid.uuid4())

        # ------------------------------------------------------------------
        # Store request ID in request.state
        # request.state is a simple namespace available throughout the request
        # Exception handlers and dependencies can access it via:
        #   request.state.request_id
        # ------------------------------------------------------------------
        request.state.request_id = request_id

        # ------------------------------------------------------------------
        # Record start time for duration calculation
        # time.time() returns seconds since Unix epoch as a float
        # ------------------------------------------------------------------
        start_time = time.time()

        # ------------------------------------------------------------------
        # Log the incoming request
        # ------------------------------------------------------------------
        logger.info(
            "Request started. request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )

        # ------------------------------------------------------------------
        # Pass control to the next layer (router, other middleware, endpoint)
        # Everything after this line runs AFTER the endpoint completes
        # ------------------------------------------------------------------
        response = await call_next(request)

        # ------------------------------------------------------------------
        # Calculate request duration in milliseconds
        # ------------------------------------------------------------------
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # ------------------------------------------------------------------
        # Log the completed request with status and duration
        # ------------------------------------------------------------------
        logger.info(
            "Request completed. request_id=%s method=%s path=%s status=%s duration=%sms",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        # ------------------------------------------------------------------
        # Add request ID to response headers
        # This allows the client (and reverse proxies) to trace the request
        # ------------------------------------------------------------------
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(duration_ms)

        return response