
from app.core.logging import setup_logging# Setup logging FIRST before anything else
setup_logging()

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import lifespan
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.system import router as system_router
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestLoggingMiddleware
from app.api.mongo_test import router as mongo_test_router
from pymongo.errors import PyMongoError
from app.core.exceptions import motor_exception_handler


logger = logging.getLogger(__name__)


def create_application() -> FastAPI:
    """
    Creates and configures the FastAPI application factory.
    """
    application = FastAPI(
        title=settings.APP_NAME,
        description="Backend API for the AI Study Assistant platform.",
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # MIDDLEWARE
    # ------------------------------------------------------------------

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.add_middleware(RequestLoggingMiddleware)

    # ------------------------------------------------------------------
    # EXCEPTION HANDLERS
    # ------------------------------------------------------------------

    register_exception_handlers(application)

    # ------------------------------------------------------------------
    # ROUTERS
    # ------------------------------------------------------------------

    application.include_router(health_router)
    application.include_router(chat_router)
    application.include_router(documents_router)
    application.include_router(system_router)
    application.include_router(mongo_test_router)
    application.add_exception_handler(PyMongoError, motor_exception_handler)

    logger.info(
        "Application ready. name=%s version=%s debug=%s origins=%s",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.DEBUG,
        settings.ALLOWED_ORIGINS,
    )

    return application


app = create_application()