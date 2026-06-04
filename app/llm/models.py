# All Pydantic models and enums used across the pipeline — inputs, outputs, and categories.
from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


class EmailCategory(str, Enum):
    """Five possible categories an email can be classified into."""
    SAMPLING = "SAMPLING"
    COSTING = "COSTING"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    GENERAL = "GENERAL"
    UNKNOWN = "UNKNOWN"


class RecommendedAction(str, Enum):
    """Actions the ops team should take based on the classification."""
    CREATE_SAMPLE_TASK = "CREATE_SAMPLE_TASK"
    REQUEST_COSTING = "REQUEST_COSTING"
    PROCESS_PURCHASE_ORDER = "PROCESS_PURCHASE_ORDER"
    NO_ACTION = "NO_ACTION"
    ESCALATE = "ESCALATE"


class ActionPriority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EmailInput(BaseModel):
    """The three fields every email must provide before entering the pipeline."""
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Full email body text")
    thread_context: str = Field(default="", description="Summary of prior thread context")


class ClassificationResult(BaseModel):
    """What Chain 1 returns — category, style IDs found, and confidence."""
    category: EmailCategory
    extracted_ids: list[str] = Field(default_factory=list)
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]


class ActionResult(BaseModel):
    """What Chain 2 returns — the action to take, its priority, and a short summary."""
    recommended_action: RecommendedAction
    priority: ActionPriority
    summary: str


class PipelineResult(BaseModel):
    """Bundles both chain outputs into one object for callers."""
    classification: ClassificationResult
    action: ActionResult
