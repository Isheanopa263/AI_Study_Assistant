import logging
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application configuration settings.

    All values are loaded from environment variables.
    Sensitive values have no defaults and must be provided.
    Non-sensitive values have safe defaults for local development.

    pydantic-settings automatically reads from:
    1. Environment variables (highest priority)
    2. .env file (local development)
    3. Default values defined here (lowest priority)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --------------------------------------------------------------------------
    # APPLICATION
    # --------------------------------------------------------------------------

    APP_NAME: str = Field(
        default="AI Study Assistant API",
        description="Name of the application.",
    )
    APP_VERSION: str = Field(
        default="1.0.0",
        description="Current version of the application.",
    )
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode. Never True in production.",
    )

    # --------------------------------------------------------------------------
    # SERVER
    # --------------------------------------------------------------------------

    HOST: str = Field(
        default="127.0.0.1",
        description="Host address for the server.",
    )
    PORT: int = Field(
        default=8000,
        description="Port for the server.",
    )

    # --------------------------------------------------------------------------
    # SECURITY
    # JWT settings will be used in Phase 5.
    # Defined here now so the structure is ready.
    # --------------------------------------------------------------------------

    JWT_SECRET: str = Field(
        default="change-this-secret-in-production",
        description="Secret key for JWT token signing. Must be changed in production.",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Algorithm used for JWT token signing.",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="Access token expiry time in minutes.",
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        description="Refresh token expiry time in days.",
    )

    # --------------------------------------------------------------------------
    # DATABASE
    # MongoDB connection will be used in Phase 3.
    # --------------------------------------------------------------------------

    MONGODB_URI: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection string (local or Atlas)",
    )
    MONGODB_DB_NAME: str = Field(
        default="study_assistant",
        description="Name of the MongoDB database",
    )

    # ── Google Gemini (Phase 4) ──
    GEMINI_API_KEY: str = Field(
            default="",
            description="Your Google Gemini API key from aistudio.google.com",
        )
    GEMINI_MODEL: str = Field(
            default="gemini-2.5-flash",
            description="The Gemini model to use. Check free-tier availability.",
        )
    GEMINI_MAX_TOKENS: int = Field(
            default=1000,
            description="Maximum tokens in the AI response.",
        )
    GEMINI_TEMPERATURE: float = Field(
            default=0.3,
            description="Creativity level: 0.0 (factual) to 2.0 (chaotic).",
        )
    GEMINI_MAX_HISTORY_MESSAGES: int = Field(
        default=20,
        description="Number of recent messages to include as context for the AI.",
    )
    GEMINI_MAX_CONTEXT_TOKENS: int = Field(
        default=8000,
        description="Maximum tokens for conversation history in each AI request.",
    )
    GEMINI_SUMMARY_THRESHOLD: int = Field(
        default=15000,
        description="Token count that triggers conversation summarization.",
    )
    
    # --------------------------------------------------------------------------
    # CORS
    # --------------------------------------------------------------------------

    ALLOWED_ORIGINS_STR: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        alias="ALLOWED_ORIGINS",
        description="Comma-separated list of allowed CORS origins.",
    )

    # --------------------------------------------------------------------------
    # LOGGING
    # --------------------------------------------------------------------------

    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level. Options: DEBUG, INFO, WARNING, ERROR, CRITICAL.",
    )

    # --------------------------------------------------------------------------
    # VALIDATORS
    # --------------------------------------------------------------------------

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Ensures LOG_LEVEL is a valid Python logging level."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(
                f"Invalid LOG_LEVEL '{value}'. Must be one of: {allowed}"
            )
        return upper

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        """Ensures JWT_ALGORITHM is a supported algorithm."""
        allowed = {"HS256", "HS384", "HS512", "RS256"}
        if value not in allowed:
            raise ValueError(
                f"Invalid JWT_ALGORITHM '{value}'. Must be one of: {allowed}"
            )
        return value

    # --------------------------------------------------------------------------
    # COMPUTED PROPERTIES
    # --------------------------------------------------------------------------

    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        """
        Parses the comma-separated ALLOWED_ORIGINS string into a list.

        .env value:   "http://localhost:3000,http://localhost:5173"
        Returns:      ["http://localhost:3000", "http://localhost:5173"]
        """
        return [
            origin.strip()
            for origin in self.ALLOWED_ORIGINS_STR.split(",")
            if origin.strip()
        ]

    @property
    def is_production(self) -> bool:
        """Returns True if the app is running in production mode."""
        return not self.DEBUG

    @property
    def mongodb_database_url(self) -> str:
        """Returns the full MongoDB connection string for logging (without password)."""
        if "@" in self.MONGODB_URL:
            # Hide password in connection string for safe logging
            parts = self.MONGODB_URL.split("@")
            return f"mongodb://***:***@{parts[-1]}"
        return self.MONGODB_URL


# ------------------------------------------------------------------------------
# SETTINGS INSTANCE
# ------------------------------------------------------------------------------
# lru_cache ensures this function is only called once.
# The same Settings instance is reused everywhere.
# This avoids reading the .env file on every import.
# ------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns the application settings instance.

    Uses lru_cache to ensure Settings is only instantiated once.
    This is the recommended pattern for FastAPI applications.

    Usage:
        from app.config import settings
        settings.APP_NAME

    Or as a dependency:
        from app.config import get_settings
        def my_endpoint(s: Settings = Depends(get_settings)):
            ...
    """
    return Settings()


# ------------------------------------------------------------------------------
# MODULE-LEVEL INSTANCE
# ------------------------------------------------------------------------------
# This allows simple imports throughout the application:
#   from app.config import settings
# ------------------------------------------------------------------------------

settings = get_settings()