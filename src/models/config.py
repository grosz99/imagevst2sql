"""
Application configuration with full validation.
NO FAKE DATA DEFAULTS - use proper configuration or fail explicitly.
"""

from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings


class SnowflakeConfig(BaseModel):
    """Snowflake connection configuration."""

    account: str = Field(..., min_length=1)
    user: str = Field(..., min_length=1)
    password: SecretStr = Field(..., min_length=8)
    warehouse: str = Field(..., min_length=1)
    database: str = Field(..., min_length=1)
    schema_name: str = Field(alias="schema", min_length=1)

    model_config = {"extra": "forbid", "populate_by_name": True}


class AnthropicConfig(BaseModel):
    """Anthropic API configuration."""

    api_key: SecretStr = Field(..., min_length=20)
    model: str = Field(default="claude-sonnet-4-20250514")
    max_tokens: int = Field(default=4096, ge=100, le=100000)

    model_config = {"extra": "forbid"}


class CaptureConfig(BaseModel):
    """Screenshot capture configuration."""

    viewport_width: int = Field(default=1920, ge=800, le=3840)
    viewport_height: int = Field(default=1080, ge=600, le=2160)
    wait_timeout_ms: int = Field(default=30000, ge=5000)
    render_delay_ms: int = Field(default=2000, ge=500)

    model_config = {"extra": "forbid"}


class Settings(BaseSettings):
    """
    Main application settings.
    CRITICAL: No fake defaults. Missing required config = explicit failure.
    """

    snowflake: Optional[SnowflakeConfig] = None
    anthropic: Optional[AnthropicConfig] = None
    capture: CaptureConfig = Field(default_factory=CaptureConfig)

    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    visual_confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)

    model_config = {
        "env_file": ".env",
        "env_nested_delimiter": "__",
        "extra": "forbid",
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings. NEVER returns fake settings."""
    return Settings()
