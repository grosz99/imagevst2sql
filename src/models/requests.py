"""
API request models.
"""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class QueryType(str, Enum):
    VISUAL = "visual"
    VERIFIED = "verified"
    SQL = "sql"
    AUTO = "auto"


class AnalyticsQuery(BaseModel):
    """A user query to the analytics system."""

    question: str = Field(..., min_length=5, max_length=1000)
    query_type: QueryType = QueryType.AUTO
    dashboard_ids: list[str] = Field(default_factory=list)
    include_sql_fallback: bool = True
    max_confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)

    @field_validator("question")
    @classmethod
    def clean_question(cls, v: str) -> str:
        return v.strip()

    model_config = {"extra": "forbid"}


class DashboardCaptureRequest(BaseModel):
    """Request to capture a dashboard screenshot."""

    dashboard_id: str = Field(..., min_length=1)
    force_refresh: bool = False
    viewport_width: Optional[int] = Field(default=None, ge=800, le=3840)
    viewport_height: Optional[int] = Field(default=None, ge=600, le=2160)
    wait_for_selector: Optional[str] = None
    extra_wait_ms: Optional[int] = Field(default=None, ge=0, le=30000)

    model_config = {"extra": "forbid"}


class GameDataRequest(BaseModel):
    """Request for NCAA basketball game data."""

    game_id: Optional[str] = None
    team_name: Optional[str] = None
    date: Optional[date] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    include_boxscore: bool = True
    include_pbp: bool = False

    @field_validator("start_date", "end_date", "date")
    @classmethod
    def validate_date_range(cls, v: Optional[date]) -> Optional[date]:
        if v is not None:
            # Season constraint: Sept 1, 2025 to Jan 9, 2026
            season_start = date(2025, 9, 1)
            season_end = date(2026, 1, 9)
            if not (season_start <= v <= season_end):
                raise ValueError(
                    f"Date must be within 2025-2026 season ({season_start} to {season_end})"
                )
        return v

    model_config = {"extra": "forbid"}


class RegisterDashboardRequest(BaseModel):
    """Request to register a new dashboard."""

    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=10)
    dashboard_type: str = Field(..., min_length=1)
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    model_config = {"extra": "forbid"}
