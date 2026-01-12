"""
Dashboard-related Pydantic models.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DashboardType(str, Enum):
    TABLEAU = "tableau"
    POWERBI = "powerbi"
    LOOKER = "looker"
    CUSTOM = "custom"


class CaptureStatus(str, Enum):
    PENDING = "pending"
    CAPTURING = "capturing"
    COMPLETED = "completed"
    FAILED = "failed"


class Dashboard(BaseModel):
    """A registered dashboard that can be captured and analyzed."""

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=10)
    dashboard_type: DashboardType
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    model_config = {"extra": "forbid"}


class DashboardCapture(BaseModel):
    """A captured screenshot of a dashboard."""

    id: str = Field(..., min_length=1)
    dashboard_id: str = Field(..., min_length=1)
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    status: CaptureStatus = CaptureStatus.PENDING
    image_path: Optional[str] = None
    image_base64: Optional[str] = None
    viewport_width: int = Field(default=1920, ge=800)
    viewport_height: int = Field(default=1080, ge=600)
    file_size_bytes: Optional[int] = Field(default=None, ge=0)
    error_message: Optional[str] = None

    model_config = {"extra": "forbid"}


class DashboardMetric(BaseModel):
    """A metric extracted from a dashboard."""

    name: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    unit: Optional[str] = None
    trend: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    position_description: Optional[str] = None

    model_config = {"extra": "forbid"}


class DashboardAnalysis(BaseModel):
    """Analysis result from visual parsing of a dashboard."""

    capture_id: str = Field(..., min_length=1)
    dashboard_id: str = Field(..., min_length=1)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    metrics: list[DashboardMetric] = Field(default_factory=list)
    key_insights: list[str] = Field(default_factory=list)
    visual_summary: Optional[str] = None
    raw_extraction: Optional[str] = None
    processing_time_ms: int = Field(..., ge=0)

    model_config = {"extra": "forbid"}
