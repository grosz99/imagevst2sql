"""
API and agent response models.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ResponseSource(str, Enum):
    VISUAL = "visual_context"
    VERIFIED = "verified_report"
    GENERATED = "generated_sql"
    ERROR = "error"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class VisualAgentResult(BaseModel):
    """
    Result from the Visual Context Agent.

    CRITICAL: Never return fake answers.
    If confidence < 0.5, answer MUST be None.
    """

    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    answer: Optional[str] = None
    dashboard_id: Optional[str] = None
    dashboard_name: Optional[str] = None
    captured_at: Optional[datetime] = None
    missing_info: Optional[str] = None
    related_metrics: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_answer_confidence(self) -> "VisualAgentResult":
        """Ensure answer is None when confidence is too low."""
        if self.confidence < 0.5 and self.answer is not None:
            raise ValueError(
                f"Answer must be None when confidence ({self.confidence}) < 0.5"
            )
        return self

    model_config = {"extra": "forbid"}


class AgentResponse(BaseModel):
    """Final response from the orchestrator."""

    answer: str = Field(..., min_length=1)
    source: ResponseSource
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    evidence: Optional[str] = None
    dashboard_reference: Optional[str] = None
    sql_query: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    processing_time_ms: Optional[int] = Field(default=None, ge=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "forbid"}
