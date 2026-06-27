from pydantic import BaseModel, Field
from typing import Optional, Any
from app.models.enums import DocumentType, DocumentQuality, DocumentIssueType

class DocumentClassification(BaseModel):
    """Result of classifying a single document."""
    file_id: str
    file_name: str = ""
    detected_type: DocumentType
    quality: DocumentQuality
    confidence: float = Field(ge=0.0, le=1.0)
    patient_name_found: Optional[str] = None
    quality_issues: list[str] = Field(default_factory=list)

class DocumentIssue(BaseModel):
    """A specific problem found during document verification."""
    issue_type: DocumentIssueType
    description: str                        # Human-readable description
    affected_document: Optional[str] = None # file_name or file_id
    details: Optional[dict] = None          # Extra context (e.g., names found)

class DocumentVerificationResult(BaseModel):
    """Output of the Document Gatekeeper agent."""
    status: str  # "PASSED" or "FAILED"
    classifications: list[DocumentClassification]
    missing_required: list[str] = Field(default_factory=list)       # List of missing DocumentType names
    unexpected_documents: list[str] = Field(default_factory=list)   # Document types found but not required
    issues: list[DocumentIssue] = Field(default_factory=list)
    error_message: Optional[str] = None     # User-facing, specific error message

class ExtractedField(BaseModel):
    """A single extracted field with confidence."""
    value: Optional[Any] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    warning: Optional[str] = None

class LineItem(BaseModel):
    """A single line item from a bill."""
    description: str
    amount: float
    category: Optional[str] = None  # Optionally classified category

class ExtractionResult(BaseModel):
    """Extracted data from a single document."""
    file_id: str
    document_type: DocumentType
    extracted_fields: dict[str, ExtractedField] = Field(default_factory=dict)
    line_items: list[LineItem] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    warnings: list[str] = Field(default_factory=list)

class ExtractedClaimData(BaseModel):
    """Aggregated extracted data across all documents for a claim."""
    documents: list[ExtractionResult]
    primary_diagnosis: Optional[str] = None
    primary_treatment: Optional[str] = None
    line_items: list[LineItem] = Field(default_factory=list)   # Consolidated from all bills
    total_extracted_amount: Optional[float] = None
    hospital_name: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_registration: Optional[str] = None
    patient_name: Optional[str] = None
    treatment_date: Optional[str] = None
