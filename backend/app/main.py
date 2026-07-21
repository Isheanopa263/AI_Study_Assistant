from fastapi import FastAPI

from app.api.health import router as health_router
from app.config import settings

app=FastAPI(
            title=settings.APP_NAME,
            description="This is the backend API for the AI Study Assistant.",
            version=settings.APP_VERSION
            )

app.include_router(health_router)