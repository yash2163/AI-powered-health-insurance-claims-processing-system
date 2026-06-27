from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import date, datetime
import uuid

from app.models.enums import ClaimCategory

class ClaimDocument(BaseModel):
    """A document attached to a claim. Supports both real uploads and test case data."""
    file_id: str
    file_name: str = ""
    # For real uploads:
    file_data: Optional[bytes] = None
    content_type: Optional[str] = None  # image/jpeg, image/png, application/pdf
    # For test cases:
    actual_type: Optional[str] = None          # Pre-declared document type
    quality: Optional[str] = None              # Pre-declared quality
    patient_name_on_doc: Optional[str] = None  # Pre-declared patient name
    content: Optional[dict[str, Any]] = None   # Pre-extracted content

    @property
    def is_test_mode(self) -> bool:
        """True if this document has pre-provided metadata (test case mode)."""
        return self.actual_type is not None

class ClaimHistoryEntry(BaseModel):
    """A prior claim from claims_history (used for fraud detection)."""
    claim_id: str
    date: str
    amount: float
    provider: Optional[str] = None

class ClaimSubmission(BaseModel):
    """The complete input for processing a claim."""
    claim_id: str = Field(default_factory=lambda: f"CLM_{uuid.uuid4().hex[:8].upper()}")
    member_id: str
    policy_id: str = "PLUM_GHI_2024"
    claim_category: ClaimCategory
    treatment_date: date
    claimed_amount: float
    hospital_name: Optional[str] = None
    documents: list[ClaimDocument]
    claims_history: Optional[list[ClaimHistoryEntry]] = None
    ytd_claims_amount: Optional[float] = None
    simulate_component_failure: bool = False
    pre_auth_approved: bool = False  # Set to True if member obtained pre-authorization
    submission_date: date = Field(default_factory=date.today)
