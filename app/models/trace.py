from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.enums import TraceStepStatus

class TraceStep(BaseModel):
    """One step in the audit trace."""
    step_name: str
    status: TraceStepStatus
    started_at: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: int = 0
    details: str = ""
    input_summary: Optional[dict] = None
    output_summary: Optional[dict] = None

class AuditTrace(BaseModel):
    """Complete audit trail for a claim."""
    claim_id: str
    steps: list[TraceStep] = Field(default_factory=list)
    component_failures: list[str] = Field(default_factory=list)

class ClaimDecision(BaseModel):
    """The final output of the claims processing pipeline."""
    claim_id: str
    decision: str  # DecisionVerdict value
    approved_amount: Optional[float] = None
    claimed_amount: float
    rejection_reasons: list[str] = Field(default_factory=list)
    confidence_score: float
    message: str  # User-facing summary message
    trace: AuditTrace
    created_at: datetime = Field(default_factory=datetime.utcnow)
