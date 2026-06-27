from pydantic import BaseModel, Field
from typing import Optional
from app.models.enums import RejectionReason, RuleSource

class PolicyCheck(BaseModel):
    """A single policy check performed during evaluation."""
    check_name: str
    passed: bool
    details: str
    source: RuleSource = RuleSource.DETERMINISTIC
    data: Optional[dict] = None  # Extra structured data for the trace

class Deduction(BaseModel):
    """A monetary deduction applied during amount calculation."""
    deduction_type: str  # NETWORK_DISCOUNT, COPAY, SUB_LIMIT_CAP, ANNUAL_LIMIT_CAP
    amount: float
    description: str

class LineItemDecision(BaseModel):
    """Decision on a single line item."""
    description: str
    amount: float
    approved: bool
    reason: Optional[str] = None  # Why it was excluded (if not approved)

class PolicyEvaluationResult(BaseModel):
    """Output of the Policy Evaluator agent."""
    checks: list[PolicyCheck] = Field(default_factory=list)
    all_checks_passed: bool = True
    rejection_reasons: list[RejectionReason] = Field(default_factory=list)
    rejection_details: list[str] = Field(default_factory=list)  # Human-readable reason per rejection
    line_item_decisions: list[LineItemDecision] = Field(default_factory=list)
    approved_line_items: list[dict] = Field(default_factory=list)
    excluded_line_items: list[dict] = Field(default_factory=list)
    pre_deduction_amount: float = 0.0
    deductions: list[Deduction] = Field(default_factory=list)
    final_approved_amount: float = 0.0
    is_partial: bool = False

class FraudSignal(BaseModel):
    """A single fraud signal detected."""
    signal_type: str
    current_value: float
    threshold: float
    description: str

class FraudCheckResult(BaseModel):
    """Output of the Fraud Detector agent."""
    signals: list[FraudSignal] = Field(default_factory=list)
    requires_manual_review: bool = False
    details: str = ""
