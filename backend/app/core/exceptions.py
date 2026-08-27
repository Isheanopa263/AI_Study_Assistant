import logging
import uuid
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# ------------------------------------------------------------------------------
# Logger setup for this module
# We will configure logging properly in Lesson 6.
# For now, this gives us basic logging capability.
# ------------------------------------------------------------------------------

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# CUSTOM EXCEPTION CLASSES
# ------------------------------------------------------------------------------
# These are domain-specific exceptions for the Study Assistant.
# Raise these in service/repository layers instead of generic exceptions.
# FastAPI exception handlers below will catch them and format responses.
# ------------------------------------------------------------------------------


class StudyAssistantException(Exception):
    """
    Base exception class for all Study Assistant errors.

    All custom exceptions should inherit from this class.
    This allows catching all application errors in one place.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "application_error",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: Optional[Any] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class NotFoundException(StudyAssistantException):
    """
    Raised when a requested resource does not exist.

    Example: student requests a chat session that was deleted.
    """

    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            message=f"{resource} with ID '{resource_id}' was not found.",
            error_code="not_found",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UnauthorizedException(StudyAssistantException):
    """
    Raised when a user is not authenticated.

    Example: request made without a valid token.
    """

    def __init__(self, message: str = "Authentication required."):
        super().__init__(
            message=message,
            error_code="unauthorized",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenException(StudyAssistantException):
    """
    Raised when a user is authenticated but not allowed to access a resource.

    Example: student tries to access another student's chat session.
    """

    def __init__(self, message: str = "You do not have permission to access this resource."):
        super().__init__(
            message=message,
            error_code="forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ValidationException(StudyAssistantException):
    """
    Raised when business logic validation fails.

    Different from Pydantic validation (which handles request format).
    This handles domain logic validation.

    Example: student tries to create more than 50 chat sessions.
    """

    def __init__(self, message: str, detail: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="validation_error",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


class AIServiceException(StudyAssistantException):
    """
    Raised when the AI provider (OpenAI/Gemini) fails or is unavailable.

    Example: OpenAI API timeout, rate limit exceeded, invalid response.
    """

    def __init__(self, message: str = "AI service is temporarily unavailable."):
        super().__init__(
            message=message,
            error_code="ai_service_error",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class DocumentProcessingException(StudyAssistantException):
    """
    Raised when document parsing or processing fails.

    Example: corrupted PDF, unsupported file type, file too large.
    """

    def __init__(self, message: str, detail: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="document_processing_error",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


# ------------------------------------------------------------------------------
# HELPER FUNCTION: Build consistent error response body
# ------------------------------------------------------------------------------


def build_error_response(
    error_code: str,
    message: str,
    request_id: str,
    detail: Optional[Any] = None,
) -> dict:
    """
    Builds a consistent error response dictionary.

    Every error response in the Study Assistant follows this exact shape.
    This ensures the React frontend can always predict the error format.
    """
    return {
        "error": error_code,
        "message": message,
        "detail": detail,
        "request_id": request_id,
    }


# ------------------------------------------------------------------------------
# EXCEPTION HANDLERS
# Register these with the FastAPI app in main.py
# ------------------------------------------------------------------------------


async def study_assistant_exception_handler(
    request: Request,
    exc: StudyAssistantException,
) -> JSONResponse:
    """
    Handles all custom StudyAssistantException subclasses.

    Logs the error and returns a structured JSON response.
    """
    request_id = getattr(request.state, "request_id", "unknown")

    logger.warning(
        "Application error occurred. "
        "request_id=%s error_code=%s message=%s",
        request_id,
        exc.error_code,
        exc.message,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_response(
            error_code=exc.error_code,
            message=exc.message,
            request_id=request_id,
            detail=exc.detail,
        ),
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    """
    Handles FastAPI's built-in HTTPException.

    Overrides the default handler to return our consistent error format.
    """
    request_id = getattr(request.state, "request_id", "unknown")

    error_code_map = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "too_many_requests",
        500: "internal_server_error",
        502: "bad_gateway",
        503: "service_unavailable",
    }

    error_code = error_code_map.get(exc.status_code, "http_error")

    logger.warning(
        "HTTP exception. request_id=%s status=%s detail=%s",
        request_id,
        exc.status_code,
        exc.detail,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_response(
            error_code=error_code,
            message=str(exc.detail),
            request_id=request_id,
        ),
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handles Pydantic RequestValidationError (422 responses).

    Formats validation errors into a clean, readable structure
    instead of FastAPI's verbose default format.
    """
    request_id = getattr(request.state, "request_id", "unknown")

    # Extract and simplify the validation error details
    errors = []
    for error in exc.errors():
        # loc is a tuple like ('body', 'content') or ('query', 'limit')
        location = " → ".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": location,
            "issue": error["msg"],
            "input": error.get("input"),
        })

    logger.warning(
        "Validation error. request_id=%s errors=%s",
        request_id,
        errors,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_error_response(
            error_code="validation_error",
            message="Request validation failed. Please check the request format.",
            request_id=request_id,
            detail=errors,
        ),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Catches ALL unhandled exceptions.

    This is the last line of defense.
    Logs the full traceback for debugging.
    Returns a safe, generic error message to the client.

    IMPORTANT: Never expose internal error details to the client.
    The full error is logged server-side only.
    """
    request_id = getattr(request.state, "request_id", "unknown")

    # Log the full exception with traceback for debugging
    logger.error(
        "Unhandled exception. request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
        exc_info=True,  # this includes the full traceback in the log
    )

    # Return safe, generic message to client
    # Never expose internal details (stack trace, DB errors, etc.)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=build_error_response(
            error_code="internal_server_error",
            message="An unexpected error occurred. Please try again later.",
            request_id=request_id,
        ),
    )


# ------------------------------------------------------------------------------
# REGISTRATION FUNCTION
# Called in main.py to register all handlers with the FastAPI app
# ------------------------------------------------------------------------------


def register_exception_handlers(app: FastAPI) -> None:
    """
    Registers all exception handlers with the FastAPI application.

    Call this function in main.py during app setup.
    Keeps main.py clean and this file self-contained.
    """
    app.add_exception_handler(StudyAssistantException, study_assistant_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)