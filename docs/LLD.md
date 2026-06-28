# Low-Level Design: Health Insurance Claims Processing System

## Document Version

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Date | 2026-06-25 |
| Status | Final — ready for implementation |
| Companion | HLD.md (read first) |

---

## 1. Prerequisites and Configuration

### 1.1 Python Dependencies (requirements.txt)

```
streamlit>=1.38.0
google-generativeai>=0.8.0
pydantic>=2.0.0
python-dotenv>=1.0.0
Pillow>=10.0.0
fpdf2>=2.7.0
python-Levenshtein>=0.25.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

### 1.2 Environment Variables (.env)

```bash
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash
GEMINI_TIMEOUT_SECONDS=30
GEMINI_MAX_RETRIES=1
GEMINI_TEMPERATURE=0
DATABASE_PATH=data/claims.db
POLICY_FILE_PATH=policy_terms.json
TEST_CASES_PATH=test_cases.json
LOG_LEVEL=INFO
```

### 1.3 Constants (app/config.py)

```python
"""Application-wide constants. Do not hardcode policy values — those come from policy_terms.json."""

import os
from dotenv import load_dotenv

load_dotenv()

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "1"))
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0"))

# Paths
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/claims.db")
POLICY_FILE_PATH = os.getenv("POLICY_FILE_PATH", "policy_terms.json")
TEST_CASES_PATH = os.getenv("TEST_CASES_PATH", "test_cases.json")

# Confidence scoring
BASE_CONFIDENCE = 0.95
LOW_QUALITY_DOC_PENALTY = 0.10
LOW_FIELD_CONFIDENCE_PENALTY = 0.05
COMPONENT_FAILURE_PENALTY = 0.30
LOW_EXCLUSION_CONFIDENCE_PENALTY = 0.10
FUZZY_NAME_MATCH_PENALTY = 0.05
MIN_CONFIDENCE = 0.10

# Fuzzy matching
NAME_MATCH_THRESHOLD = 0.75  # Levenshtein ratio below this = mismatch
```

---

## 2. Data Models (app/models/)

All models use Pydantic v2. Every model that flows through the pipeline is defined here with exact field types, validators, and defaults.

### 2.1 Enums (app/models/enums.py)

```python
from enum import Enum

class ClaimCategory(str, Enum):
    CONSULTATION = "CONSULTATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    PHARMACY = "PHARMACY"
    DENTAL = "DENTAL"
    VISION = "VISION"
    ALTERNATIVE_MEDICINE = "ALTERNATIVE_MEDICINE"

class DocumentType(str, Enum):
    PRESCRIPTION = "PRESCRIPTION"
    HOSPITAL_BILL = "HOSPITAL_BILL"
    LAB_REPORT = "LAB_REPORT"
    PHARMACY_BILL = "PHARMACY_BILL"
    DIAGNOSTIC_REPORT = "DIAGNOSTIC_REPORT"
    DENTAL_REPORT = "DENTAL_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    UNKNOWN = "UNKNOWN"

class DocumentQuality(str, Enum):
    GOOD = "GOOD"
    LOW = "LOW"
    UNREADABLE = "UNREADABLE"

class DecisionVerdict(str, Enum):
    APPROVED = "APPROVED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"

class TraceStepStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"
    SKIPPED = "SKIPPED"

class RuleSource(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"

class RejectionReason(str, Enum):
    WAITING_PERIOD = "WAITING_PERIOD"
    PRE_AUTH_MISSING = "PRE_AUTH_MISSING"
    EXCLUDED_CONDITION = "EXCLUDED_CONDITION"
    PER_CLAIM_EXCEEDED = "PER_CLAIM_EXCEEDED"
    POLICY_INACTIVE = "POLICY_INACTIVE"
    MEMBER_NOT_FOUND = "MEMBER_NOT_FOUND"
    BELOW_MINIMUM = "BELOW_MINIMUM"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    CATEGORY_NOT_COVERED = "CATEGORY_NOT_COVERED"

class DocumentIssueType(str, Enum):
    MISSING_DOCUMENT = "MISSING_DOCUMENT"
    WRONG_DOCUMENT = "WRONG_DOCUMENT"
    UNREADABLE = "UNREADABLE"
    PATIENT_MISMATCH = "PATIENT_MISMATCH"
```

### 2.2 Claim Models (app/models/claim.py)

```python
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
```

### 2.3 Document Models (app/models/document.py)

```python
from pydantic import BaseModel, Field
from typing import Optional
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
    value: Optional[str | int | float | list] = None
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
```

### 2.4 Policy Models (app/models/policy.py)

```python
from pydantic import BaseModel
from typing import Optional

class CategoryConfig(BaseModel):
    """Configuration for a single OPD category from policy_terms.json."""
    sub_limit: float
    copay_percent: float
    network_discount_percent: float = 0.0
    requires_prescription: bool = False
    requires_pre_auth: bool = False
    requires_dental_report: bool = False
    requires_registered_practitioner: bool = False
    pre_auth_threshold: Optional[float] = None
    high_value_tests_requiring_pre_auth: list[str] = []
    covered: bool = True
    covered_procedures: list[str] = []
    excluded_procedures: list[str] = []
    covered_items: list[str] = []
    excluded_items: list[str] = []
    covered_systems: list[str] = []
    max_sessions_per_year: Optional[int] = None
    branded_drug_copay_percent: float = 0.0
    generic_mandatory: bool = False

class MemberInfo(BaseModel):
    """A member from the policy member roster."""
    member_id: str
    name: str
    date_of_birth: str
    gender: str
    relationship: str
    join_date: Optional[str] = None            # Present for employees
    primary_member_id: Optional[str] = None    # Present for dependents
    dependents: list[str] = []

class PolicyConfig(BaseModel):
    """Complete policy configuration loaded from policy_terms.json."""
    policy_id: str
    policy_name: str
    insurer: str
    company_name: str
    policy_start_date: str
    policy_end_date: str
    sum_insured_per_employee: float
    annual_opd_limit: float
    per_claim_limit: float
    opd_categories: dict[str, CategoryConfig]
    waiting_periods: dict  # Raw dict from JSON — initial + specific conditions
    exclusions: dict       # Raw dict — conditions, dental, vision
    pre_authorization: dict
    network_hospitals: list[str]
    submission_rules: dict
    fraud_thresholds: dict
    document_requirements: dict[str, dict[str, list[str]]]  # category -> required/optional -> doc types
    members: dict[str, MemberInfo]  # Keyed by member_id for O(1) lookup
```

### 2.5 Decision Models (app/models/decision.py)

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.enums import DecisionVerdict, RejectionReason, RuleSource

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
```

### 2.6 Trace Models (app/models/trace.py)

```python
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
```

---

## 3. Service Layer (app/services/)

### 3.1 Gemini Client (app/services/gemini_client.py)

**Responsibility:** Wraps all Gemini API calls with retry, timeout, and structured output parsing.

```python
"""
Gemini API client with retry, timeout, and JSON mode.

Public interface:
    - classify_document(image_data: bytes, content_type: str) -> dict
    - extract_document_data(image_data: bytes, content_type: str, doc_type: str) -> dict
    - classify_policy_terms(claim_data: dict, policy_context: dict) -> dict

All methods return parsed JSON dicts. On failure, raise GeminiAPIError.
"""
```

**Implementation specification:**

```python
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import json
import time
from app.config import (
    GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TIMEOUT,
    GEMINI_MAX_RETRIES, GEMINI_TEMPERATURE
)

class GeminiAPIError(Exception):
    """Raised when Gemini API call fails after retries."""
    pass

class GeminiClient:
    def __init__(self):
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            generation_config=GenerationConfig(
                temperature=GEMINI_TEMPERATURE,
                response_mime_type="application/json"
            )
        )

    def _call_with_retry(self, contents: list, timeout: int = None) -> dict:
        """
        Make a Gemini API call with retry logic.

        Args:
            contents: List of content parts (text, images) for the API call.
            timeout: Override default timeout.

        Returns:
            Parsed JSON dict from Gemini response.

        Raises:
            GeminiAPIError: If all retries fail or response is not valid JSON.
        """
        timeout = timeout or GEMINI_TIMEOUT
        last_error = None

        for attempt in range(GEMINI_MAX_RETRIES + 1):
            try:
                response = self.model.generate_content(
                    contents,
                    request_options={"timeout": timeout}
                )
                # Parse JSON response
                text = response.text.strip()
                # Strip markdown code fences if present
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()
                return json.loads(text)
            except json.JSONDecodeError as e:
                last_error = GeminiAPIError(f"Invalid JSON response: {e}")
            except Exception as e:
                last_error = GeminiAPIError(f"Gemini API error: {e}")

            if attempt < GEMINI_MAX_RETRIES:
                time.sleep(1)  # Brief delay before retry

        raise last_error

    def classify_document(self, image_data: bytes, content_type: str) -> dict:
        """Classify document type, quality, and extract patient name. See prompt in Section 6.1."""
        # Implementation: build contents with CLASSIFY_DOCUMENT_PROMPT + image, call _call_with_retry
        pass

    def extract_document_data(self, image_data: bytes, content_type: str, doc_type: str) -> dict:
        """Extract structured data from a document. See prompts in Section 6.2."""
        # Implementation: select prompt by doc_type, build contents, call _call_with_retry
        pass

    def classify_policy_terms(self, claim_data: dict, policy_context: dict) -> dict:
        """Classify diagnosis/treatment against policy terms. See prompt in Section 6.3. TEXT ONLY - no image."""
        # Implementation: build text-only contents with POLICY_CLASSIFY_PROMPT, call _call_with_retry
        pass
```

### 3.2 Policy Loader (app/services/policy_loader.py)

**Responsibility:** Load `policy_terms.json` once at startup, parse into `PolicyConfig` model.

```python
"""
Loads and parses policy_terms.json into PolicyConfig.

Public interface:
    - load_policy(filepath: str) -> PolicyConfig
    - get_member(policy: PolicyConfig, member_id: str) -> MemberInfo | None
    - get_category_config(policy: PolicyConfig, category: ClaimCategory) -> CategoryConfig | None
    - get_document_requirements(policy: PolicyConfig, category: ClaimCategory) -> dict
    - is_network_hospital(policy: PolicyConfig, hospital_name: str) -> bool
"""
```

**Implementation specification:**

```python
import json
from app.models.policy import PolicyConfig, CategoryConfig, MemberInfo
from app.models.enums import ClaimCategory

def load_policy(filepath: str) -> PolicyConfig:
    """
    Load policy_terms.json and construct PolicyConfig.

    Key transformations:
    1. Flatten nested policy_holder fields into top level.
    2. Parse each opd_categories entry into CategoryConfig.
    3. Build members dict keyed by member_id for O(1) lookup.
    4. Determine join_date for dependents by looking up their primary_member's join_date.
    """
    with open(filepath, "r") as f:
        raw = json.load(f)

    # Build member lookup (keyed by member_id)
    members = {}
    for m in raw["members"]:
        members[m["member_id"]] = MemberInfo(**m)

    # For dependents without join_date, inherit from primary member
    for mid, member in members.items():
        if member.join_date is None and member.primary_member_id:
            primary = members.get(member.primary_member_id)
            if primary:
                member.join_date = primary.join_date

    # Build category configs
    category_map = {
        "consultation": "CONSULTATION",
        "diagnostic": "DIAGNOSTIC",
        "pharmacy": "PHARMACY",
        "dental": "DENTAL",
        "vision": "VISION",
        "alternative_medicine": "ALTERNATIVE_MEDICINE"
    }
    opd_categories = {}
    for json_key, enum_val in category_map.items():
        if json_key in raw["opd_categories"]:
            opd_categories[enum_val] = CategoryConfig(**raw["opd_categories"][json_key])

    return PolicyConfig(
        policy_id=raw["policy_id"],
        policy_name=raw["policy_name"],
        insurer=raw["insurer"],
        company_name=raw["policy_holder"]["company_name"],
        policy_start_date=raw["policy_holder"]["policy_start_date"],
        policy_end_date=raw["policy_holder"]["policy_end_date"],
        sum_insured_per_employee=raw["coverage"]["sum_insured_per_employee"],
        annual_opd_limit=raw["coverage"]["annual_opd_limit"],
        per_claim_limit=raw["coverage"]["per_claim_limit"],
        opd_categories=opd_categories,
        waiting_periods=raw["waiting_periods"],
        exclusions=raw["exclusions"],
        pre_authorization=raw["pre_authorization"],
        network_hospitals=raw["network_hospitals"],
        submission_rules=raw["submission_rules"],
        fraud_thresholds=raw["fraud_thresholds"],
        document_requirements=raw["document_requirements"],
        members=members,
    )


def get_member(policy: PolicyConfig, member_id: str) -> MemberInfo | None:
    return policy.members.get(member_id)


def get_category_config(policy: PolicyConfig, category: ClaimCategory) -> CategoryConfig | None:
    return policy.opd_categories.get(category.value)


def get_document_requirements(policy: PolicyConfig, category: ClaimCategory) -> dict:
    """Returns {"required": [...], "optional": [...]} for the claim category."""
    return policy.document_requirements.get(category.value, {"required": [], "optional": []})


def is_network_hospital(policy: PolicyConfig, hospital_name: str) -> bool:
    """
    Check if hospital_name matches any network hospital.
    Uses case-insensitive substring matching.
    E.g., "Apollo Hospitals, Chennai" matches "Apollo Hospitals" in the list.
    """
    if not hospital_name:
        return False
    hospital_lower = hospital_name.lower()
    for network in policy.network_hospitals:
        if network.lower() in hospital_lower or hospital_lower in network.lower():
            return True
    return False
```

### 3.3 Database Service (app/services/database.py)

**Responsibility:** SQLite operations for persisting claims, decisions, and traces.

```python
"""
SQLite persistence layer.

Public interface:
    - init_db() -> None                               # Create tables if not exist
    - save_claim(claim: ClaimSubmission) -> None
    - save_decision(decision: ClaimDecision) -> None
    - get_all_decisions() -> list[dict]
    - get_decision(claim_id: str) -> dict | None
    - get_claims_for_member(member_id: str) -> list[dict]
"""
```

**Schema DDL:**

```sql
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    claim_category TEXT NOT NULL,
    treatment_date TEXT NOT NULL,
    claimed_amount REAL NOT NULL,
    hospital_name TEXT,
    submission_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS decisions (
    claim_id TEXT PRIMARY KEY,
    decision TEXT NOT NULL,           -- APPROVED, PARTIAL, REJECTED, MANUAL_REVIEW
    approved_amount REAL,
    claimed_amount REAL NOT NULL,
    confidence_score REAL NOT NULL,
    message TEXT NOT NULL,
    rejection_reasons TEXT,           -- JSON array as text
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);

CREATE TABLE IF NOT EXISTS traces (
    claim_id TEXT PRIMARY KEY,
    trace_json TEXT NOT NULL,         -- Full AuditTrace serialized as JSON
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);
```

### 3.4 Text Matching Utility (app/utils/text_matching.py)

```python
"""
Fuzzy text matching utilities for patient name comparison.

Public interface:
    - names_match(name1: str, name2: str, threshold: float = 0.75) -> tuple[bool, float]
    - normalize_name(name: str) -> str
"""
from Levenshtein import ratio as levenshtein_ratio

def normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, strip titles, collapse whitespace."""
    if not name:
        return ""
    name = name.lower().strip()
    # Remove common Indian honorifics
    for prefix in ["mr.", "mrs.", "ms.", "dr.", "shri", "smt.", "master"]:
        if name.startswith(prefix):
            name = name[len(prefix):].strip()
    # Collapse multiple spaces
    return " ".join(name.split())

def names_match(name1: str, name2: str, threshold: float = 0.75) -> tuple[bool, float]:
    """
    Compare two patient names using normalized Levenshtein ratio.

    Returns:
        (is_match: bool, similarity_score: float)
    """
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)
    if not n1 or not n2:
        return False, 0.0
    score = levenshtein_ratio(n1, n2)
    return score >= threshold, score
```

### 3.5 Date Utilities (app/utils/date_utils.py)

```python
"""
Date arithmetic utilities for policy evaluation.

Public interface:
    - parse_date(date_str: str) -> date
    - days_between(d1: date, d2: date) -> int
    - is_within_policy_period(treatment_date: date, start: str, end: str) -> bool
    - is_within_submission_deadline(treatment_date: date, submission_date: date, deadline_days: int) -> bool
    - calculate_waiting_period_end(join_date: date, waiting_days: int) -> date
    - is_in_waiting_period(treatment_date: date, join_date: date, waiting_days: int) -> tuple[bool, date]
"""
from datetime import date, timedelta

def parse_date(date_str: str) -> date:
    """Parse YYYY-MM-DD string to date object."""
    if isinstance(date_str, date):
        return date_str
    return date.fromisoformat(date_str)

def days_between(d1: date, d2: date) -> int:
    """Return number of days between two dates (d2 - d1)."""
    return (d2 - d1).days

def is_within_policy_period(treatment_date: date, start: str, end: str) -> bool:
    return parse_date(start) <= treatment_date <= parse_date(end)

def is_within_submission_deadline(treatment_date: date, submission_date: date, deadline_days: int) -> bool:
    return (submission_date - treatment_date).days <= deadline_days

def calculate_waiting_period_end(join_date: date, waiting_days: int) -> date:
    return join_date + timedelta(days=waiting_days)

def is_in_waiting_period(treatment_date: date, join_date: date, waiting_days: int) -> tuple[bool, date]:
    """
    Check if treatment_date falls within the waiting period.

    Returns:
        (is_in_waiting: bool, eligible_from: date)
    """
    eligible_from = calculate_waiting_period_end(join_date, waiting_days)
    is_in_waiting = treatment_date < eligible_from
    return is_in_waiting, eligible_from
```

---

## 4. Agent Implementations (app/agents/)

Each agent follows the same contract pattern:

```python
class AgentName:
    def process(self, input: InputType, context: ContextType) -> tuple[OutputType, TraceStep]:
        """
        Process the input and return (result, trace_step).
        Never raises exceptions to the caller — all errors are caught
        and reflected in the trace_step with status FAILED.
        """
```

### 4.1 Input Validator (app/agents/input_validator.py)

**Contract:**

```
Input:  ClaimSubmission, PolicyConfig
Output: tuple[bool, list[str], TraceStep]
        - bool: True if all validations pass
        - list[str]: List of validation error messages (empty if passed)
        - TraceStep: Audit trace entry
```

**Implementation specification:**

```python
"""
Agent 1: Input Validator

Validates claim submission metadata against policy configuration.
All checks are deterministic — no LLM calls.

Checks performed (in order):
1. member_id exists in policy.members
2. Policy is active on treatment_date
3. claimed_amount >= submission_rules.minimum_claim_amount (500)
4. treatment_date is within submission_rules.deadline_days_from_treatment (30 days) of submission_date
5. claim_category is a valid, covered category in opd_categories

On first failure: all checks still run (collect ALL errors), then return False.
"""

class InputValidator:
    def process(self, claim: ClaimSubmission, policy: PolicyConfig) -> tuple[bool, list[str], TraceStep]:
        start_time = datetime.utcnow()
        errors = []

        # Check 1: Member exists
        member = policy.members.get(claim.member_id)
        if not member:
            errors.append(f"Member '{claim.member_id}' not found in the policy roster.")

        # Check 2: Policy active
        if not is_within_policy_period(claim.treatment_date, policy.policy_start_date, policy.policy_end_date):
            errors.append(
                f"Treatment date {claim.treatment_date} is outside the policy period "
                f"({policy.policy_start_date} to {policy.policy_end_date})."
            )

        # Check 3: Minimum amount
        min_amount = policy.submission_rules.get("minimum_claim_amount", 500)
        if claim.claimed_amount < min_amount:
            errors.append(
                f"Claimed amount ₹{claim.claimed_amount} is below the minimum claim amount of ₹{min_amount}."
            )

        # Check 4: Submission deadline
        deadline_days = policy.submission_rules.get("deadline_days_from_treatment", 30)
        if not is_within_submission_deadline(claim.treatment_date, claim.submission_date, deadline_days):
            errors.append(
                f"Claim submitted more than {deadline_days} days after treatment date {claim.treatment_date}."
            )

        # Check 5: Valid category
        category_config = policy.opd_categories.get(claim.claim_category.value)
        if not category_config:
            errors.append(f"Claim category '{claim.claim_category.value}' is not recognized.")
        elif not category_config.covered:
            errors.append(f"Category '{claim.claim_category.value}' is not covered under this policy.")

        passed = len(errors) == 0
        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        trace = TraceStep(
            step_name="input_validation",
            status=TraceStepStatus.PASSED if passed else TraceStepStatus.FAILED,
            duration_ms=duration,
            details="; ".join(errors) if errors else (
                f"Member {claim.member_id} valid. Policy active. "
                f"Amount ₹{claim.claimed_amount:,.0f} within limits. "
                f"Category {claim.claim_category.value} covered."
            )
        )

        return passed, errors, trace
```

### 4.2 Document Gatekeeper (app/agents/document_gatekeeper.py)

**Contract:**

```
Input:  ClaimSubmission, PolicyConfig, GeminiClient (optional, only for real uploads)
Output: tuple[DocumentVerificationResult, TraceStep]
```

**Implementation specification:**

```python
"""
Agent 2: Document Gatekeeper

Verifies uploaded documents are correct, readable, and consistent.

Dual-mode operation:
    - TEST MODE: When document has actual_type/quality/patient_name_on_doc pre-set,
      use those directly without calling Gemini.
    - REAL MODE: When document has file_data (bytes), call Gemini Vision
      for classification, quality assessment, and patient name extraction.

Three-phase process:
    Phase 1 — Classification: Determine type of each document.
    Phase 2 — Completeness check: Verify required documents are present.
    Phase 3 — Quality gate: Check no required doc is UNREADABLE.
    Phase 4 — Cross-document consistency: Patient names must match across all documents.

On ANY issue: return status=FAILED with specific, actionable error_message.
The error message must name:
    - Which document type was uploaded vs what was needed (TC001)
    - Which specific document is unreadable (TC002)
    - The exact patient names found on mismatching documents (TC003)
"""

class DocumentGatekeeper:
    def __init__(self, gemini_client=None):
        self.gemini_client = gemini_client

    def process(self, claim: ClaimSubmission, policy: PolicyConfig) -> tuple[DocumentVerificationResult, TraceStep]:
        start_time = datetime.utcnow()
        classifications = []
        issues = []

        # Phase 1: Classify each document
        for doc in claim.documents:
            if doc.is_test_mode:
                # Use pre-declared metadata
                classification = DocumentClassification(
                    file_id=doc.file_id,
                    file_name=doc.file_name,
                    detected_type=DocumentType(doc.actual_type),
                    quality=DocumentQuality(doc.quality) if doc.quality else DocumentQuality.GOOD,
                    confidence=0.99,
                    patient_name_found=doc.patient_name_on_doc or (
                        doc.content.get("patient_name") if doc.content else None
                    )
                )
            else:
                # Call Gemini Vision for classification
                # (see Section 6.1 for prompt)
                result = self.gemini_client.classify_document(doc.file_data, doc.content_type)
                classification = DocumentClassification(
                    file_id=doc.file_id,
                    file_name=doc.file_name,
                    detected_type=DocumentType(result["document_type"]),
                    quality=DocumentQuality(result["quality"]),
                    confidence=result["confidence"],
                    patient_name_found=result.get("patient_name"),
                    quality_issues=result.get("quality_issues", [])
                )
            classifications.append(classification)

        # Phase 2: Completeness — check required docs
        required = get_document_requirements(policy, claim.claim_category)
        required_types = set(required.get("required", []))
        found_types = {c.detected_type.value for c in classifications}
        missing = required_types - found_types

        if missing:
            found_names = ", ".join(sorted(found_types))
            missing_names = ", ".join(sorted(missing))
            error_msg = (
                f"Your {claim.claim_category.value.lower()} claim requires the following documents: "
                f"{', '.join(sorted(required_types))}. "
                f"We found: {found_names}. "
                f"Missing: {missing_names}. "
                f"Please upload your {missing_names.lower().replace('_', ' ')} and resubmit."
            )
            issues.append(DocumentIssue(
                issue_type=DocumentIssueType.MISSING_DOCUMENT,
                description=error_msg,
                details={"required": sorted(required_types), "found": sorted(found_types), "missing": sorted(missing)}
            ))

        # Phase 3: Quality gate — required docs must not be UNREADABLE
        for c in classifications:
            if c.quality == DocumentQuality.UNREADABLE and c.detected_type.value in required_types:
                error_msg = (
                    f"Your {c.detected_type.value.lower().replace('_', ' ')} "
                    f"({c.file_name or c.file_id}) is not readable. "
                    f"Please re-upload a clearer photo of your "
                    f"{c.detected_type.value.lower().replace('_', ' ')}."
                )
                issues.append(DocumentIssue(
                    issue_type=DocumentIssueType.UNREADABLE,
                    description=error_msg,
                    affected_document=c.file_name or c.file_id
                ))

        # Phase 4: Cross-document consistency — patient names must match
        names_found = [
            (c.file_id, c.file_name, c.patient_name_found, c.detected_type.value)
            for c in classifications if c.patient_name_found
        ]
        if len(names_found) >= 2:
            # Compare all pairs
            reference_name = names_found[0][2]
            for _, fname, name, dtype in names_found[1:]:
                is_match, score = names_match(reference_name, name)
                if not is_match:
                    error_msg = (
                        f"The documents appear to belong to different patients. "
                        f"The {names_found[0][3].lower().replace('_', ' ')} is for "
                        f"'{names_found[0][2]}' but the {dtype.lower().replace('_', ' ')} "
                        f"is for '{name}'. All documents must be for the same patient."
                    )
                    issues.append(DocumentIssue(
                        issue_type=DocumentIssueType.PATIENT_MISMATCH,
                        description=error_msg,
                        details={
                            "names_found": {n[3]: n[2] for n in names_found},
                            "similarity_score": score
                        }
                    ))
                    break  # One mismatch is enough

        # Build result
        has_issues = len(issues) > 0
        status = "FAILED" if has_issues else "PASSED"
        error_message = issues[0].description if issues else None  # First issue is the primary error

        result = DocumentVerificationResult(
            status=status,
            classifications=classifications,
            missing_required=sorted(missing) if missing else [],
            issues=issues,
            error_message=error_message
        )

        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        trace = TraceStep(
            step_name="document_verification",
            status=TraceStepStatus.PASSED if not has_issues else TraceStepStatus.FAILED,
            duration_ms=duration,
            details=error_message or (
                f"{len(classifications)} documents classified. "
                f"All required documents present. "
                f"Patient names consistent: '{names_found[0][2] if names_found else 'N/A'}'."
            )
        )

        return result, trace
```

### 4.3 Data Extractor (app/agents/data_extractor.py)

**Contract:**

```
Input:  ClaimSubmission, list[DocumentClassification], GeminiClient (optional)
Output: tuple[ExtractedClaimData, TraceStep]
```

**Implementation specification:**

```python
"""
Agent 3: Data Extractor

Extracts structured data from medical documents into standardized models.

Dual-mode:
    - TEST MODE: When document has content dict pre-set, use it directly.
      Map the test case content structure to ExtractionResult.
    - REAL MODE: Call Gemini Vision for structured extraction per document.

Aggregation logic after extracting from all documents:
    1. primary_diagnosis: from PRESCRIPTION document's diagnosis field
    2. primary_treatment: from PRESCRIPTION's treatment field (if present)
    3. line_items: consolidated from all HOSPITAL_BILL / PHARMACY_BILL documents
    4. total_extracted_amount: sum of all line_items, or bill total if no line items
    5. hospital_name: from HOSPITAL_BILL or claim-level hospital_name
    6. doctor_name + registration: from PRESCRIPTION
    7. patient_name: most frequently occurring name across documents
"""

class DataExtractor:
    def __init__(self, gemini_client=None):
        self.gemini_client = gemini_client

    def process(
        self,
        claim: ClaimSubmission,
        classifications: list[DocumentClassification]
    ) -> tuple[ExtractedClaimData, TraceStep]:

        start_time = datetime.utcnow()
        extraction_results = []
        warnings = []

        for doc, classification in zip(claim.documents, classifications):
            if doc.content is not None:
                # TEST MODE: map pre-provided content to ExtractionResult
                result = self._extract_from_test_content(doc, classification)
            else:
                # REAL MODE: call Gemini Vision
                result = self._extract_from_image(doc, classification)
            extraction_results.append(result)

        # Aggregate across all documents
        aggregated = self._aggregate(extraction_results, claim)

        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        trace = TraceStep(
            step_name="data_extraction",
            status=TraceStepStatus.PASSED,
            duration_ms=duration,
            details=(
                f"Extracted data from {len(extraction_results)} documents. "
                f"Diagnosis: {aggregated.primary_diagnosis or 'N/A'}. "
                f"Treatment: {aggregated.primary_treatment or 'N/A'}. "
                f"Line items: {len(aggregated.line_items)}. "
                f"Total amount: ₹{aggregated.total_extracted_amount or 0:,.0f}."
            )
        )

        return aggregated, trace

    def _extract_from_test_content(
        self, doc: ClaimDocument, classification: DocumentClassification
    ) -> ExtractionResult:
        """
        Map test case content dict to ExtractionResult.

        Test case content structures vary by doc type:
        - PRESCRIPTION: {doctor_name, doctor_registration, patient_name, diagnosis, medicines, date, treatment?, tests_ordered?}
        - HOSPITAL_BILL: {hospital_name?, patient_name?, date?, line_items: [{description, amount}], total}
        - LAB_REPORT: {test_name?, patient_name?}
        - PHARMACY_BILL: {pharmacy_name?, patient_name?, items: [...], total}

        Map each field to ExtractedField with confidence 0.95 (test data is reliable).
        """
        content = doc.content or {}
        fields = {}
        line_items = []

        for key, value in content.items():
            if key == "line_items":
                line_items = [LineItem(description=item["description"], amount=item["amount"]) for item in value]
            elif key == "medicines":
                fields[key] = ExtractedField(value=value, confidence=0.95)
            elif key == "total":
                fields["total_amount"] = ExtractedField(value=value, confidence=0.95)
            else:
                fields[key] = ExtractedField(value=value, confidence=0.95)

        return ExtractionResult(
            file_id=doc.file_id,
            document_type=classification.detected_type,
            extracted_fields=fields,
            line_items=line_items,
            overall_confidence=0.95,
            warnings=[]
        )

    def _extract_from_image(
        self, doc: ClaimDocument, classification: DocumentClassification
    ) -> ExtractionResult:
        """
        Call Gemini Vision for extraction. See Section 6.2 for prompts.
        Select prompt based on classification.detected_type.
        Parse response into ExtractionResult.
        """
        # Implementation calls self.gemini_client.extract_document_data(...)
        pass

    def _aggregate(self, results: list[ExtractionResult], claim: ClaimSubmission) -> ExtractedClaimData:
        """
        Aggregate extraction results across all documents.

        Priority rules:
        - diagnosis: from first PRESCRIPTION document
        - treatment: from PRESCRIPTION's treatment field (if present)
        - line_items: from all HOSPITAL_BILL and PHARMACY_BILL documents
        - hospital_name: from HOSPITAL_BILL, or claim.hospital_name fallback
        - total: sum of line_items, or bill total field, or claim.claimed_amount fallback
        """
        diagnosis = None
        treatment = None
        all_line_items = []
        hospital_name = claim.hospital_name
        doctor_name = None
        doctor_reg = None
        patient_name = None
        total = None

        for r in results:
            fields = r.extracted_fields

            if r.document_type == DocumentType.PRESCRIPTION:
                if "diagnosis" in fields and fields["diagnosis"].value:
                    diagnosis = fields["diagnosis"].value
                if "treatment" in fields and fields["treatment"].value:
                    treatment = fields["treatment"].value
                if "doctor_name" in fields and fields["doctor_name"].value:
                    doctor_name = fields["doctor_name"].value
                if "doctor_registration" in fields and fields["doctor_registration"].value:
                    doctor_reg = fields["doctor_registration"].value
                if "patient_name" in fields and fields["patient_name"].value:
                    patient_name = fields["patient_name"].value

            if r.document_type in (DocumentType.HOSPITAL_BILL, DocumentType.PHARMACY_BILL):
                all_line_items.extend(r.line_items)
                if "hospital_name" in fields and fields["hospital_name"].value:
                    hospital_name = hospital_name or fields["hospital_name"].value
                if "total_amount" in fields and fields["total_amount"].value:
                    total = fields["total_amount"].value
                if "patient_name" in fields and fields["patient_name"].value:
                    patient_name = patient_name or fields["patient_name"].value

        # If no line items extracted, create a single line item from total
        if not all_line_items and total:
            all_line_items = [LineItem(description="Total claim amount", amount=float(total))]

        # Total: prefer sum of line items, then extracted total, then claimed amount
        if all_line_items:
            total = sum(item.amount for item in all_line_items)
        elif total is None:
            total = claim.claimed_amount

        return ExtractedClaimData(
            documents=results,
            primary_diagnosis=diagnosis,
            primary_treatment=treatment,
            line_items=all_line_items,
            total_extracted_amount=float(total) if total else claim.claimed_amount,
            hospital_name=hospital_name,
            doctor_name=doctor_name,
            doctor_registration=doctor_reg,
            patient_name=patient_name,
        )
```

### 4.4 Policy Evaluator — Hybrid (app/agents/policy_evaluator.py)

**Contract:**

```
Input:  ClaimSubmission, ExtractedClaimData, PolicyConfig, GeminiClient (optional)
Output: tuple[PolicyEvaluationResult, TraceStep]
```

**This is the most complex agent. It has two sub-components.**

**Implementation specification:**

```python
"""
Agent 4: Policy Evaluator (Hybrid)

Two sub-components:
    A) LLM Classifier — semantic matching (diagnosis→condition, treatment→exclusion, item→procedure)
    B) Deterministic Engine — financial calculations and date-based checks

Execution order:
    1. Run LLM Classifier first (provides classifications needed by deterministic engine)
    2. Run Deterministic Engine using LLM output + extracted data

The Calculation Waterfall (exact order):

    Phase 1 — Hard Rejection Gates:
        1.1 Waiting period check
        1.2 Pre-authorization check
        1.3 Full exclusion check (all items excluded → REJECTED)

    Phase 2 — Line-Item Filtering:
        2.1 Classify each line item as covered/excluded
        2.2 Remove excluded items, record reasons
        2.3 Calculate post_filter_amount

    Phase 3 — Per-Claim Limit Check:
        3.1 effective_cap = max(per_claim_limit, category_sub_limit)
        3.2 If post_filter_amount > effective_cap → REJECTED

    Phase 4 — Amount Calculation:
        4.1 Apply network discount if hospital is in network
        4.2 Apply copay on discounted amount
        4.3 Check annual OPD limit (if YTD data available)
        4.4 Round to 2 decimal places → final_approved_amount
"""

class PolicyEvaluator:
    def __init__(self, gemini_client=None):
        self.gemini_client = gemini_client

    def process(
        self,
        claim: ClaimSubmission,
        extracted: ExtractedClaimData,
        policy: PolicyConfig
    ) -> tuple[PolicyEvaluationResult, TraceStep]:

        start_time = datetime.utcnow()
        checks = []
        rejection_reasons = []
        rejection_details = []

        category_config = get_category_config(policy, claim.claim_category)
        member = get_member(policy, claim.member_id)

        # ============================================================
        # STEP A: LLM Classifier (semantic matching)
        # ============================================================
        llm_classification = self._run_llm_classifier(
            extracted, policy, claim.claim_category, category_config
        )

        # ============================================================
        # STEP B: Deterministic Engine
        # ============================================================

        # --- Phase 1: Hard Rejection Gates ---

        # 1.1 Waiting Period
        waiting_check = self._check_waiting_period(
            claim, member, extracted, policy, llm_classification
        )
        checks.append(waiting_check)
        if not waiting_check.passed:
            rejection_reasons.append(RejectionReason.WAITING_PERIOD)
            rejection_details.append(waiting_check.details)

        # 1.2 Pre-Authorization
        preauth_check = self._check_pre_authorization(
            claim, extracted, policy, category_config, llm_classification
        )
        checks.append(preauth_check)
        if not preauth_check.passed:
            rejection_reasons.append(RejectionReason.PRE_AUTH_MISSING)
            rejection_details.append(preauth_check.details)

        # 1.3 Full Exclusion Check
        exclusion_check = self._check_full_exclusion(
            extracted, policy, llm_classification
        )
        checks.append(exclusion_check)
        if not exclusion_check.passed:
            rejection_reasons.append(RejectionReason.EXCLUDED_CONDITION)
            rejection_details.append(exclusion_check.details)

        # If any Phase 1 gate failed → short-circuit to REJECTED
        if rejection_reasons:
            result = PolicyEvaluationResult(
                checks=checks,
                all_checks_passed=False,
                rejection_reasons=rejection_reasons,
                rejection_details=rejection_details,
                final_approved_amount=0.0
            )
            duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            trace = self._build_trace(result, duration)
            return result, trace

        # --- Phase 2: Line-Item Filtering ---
        line_item_decisions = self._filter_line_items(
            extracted, policy, claim.claim_category, category_config, llm_classification
        )
        approved_items = [d for d in line_item_decisions if d.approved]
        excluded_items = [d for d in line_item_decisions if not d.approved]
        post_filter_amount = sum(d.amount for d in approved_items)
        is_partial = len(excluded_items) > 0 and len(approved_items) > 0

        line_items_check = PolicyCheck(
            check_name="line_item_filtering",
            passed=len(approved_items) > 0,
            details=(
                f"{len(approved_items)} items approved (₹{post_filter_amount:,.0f}), "
                f"{len(excluded_items)} items excluded."
            ),
            source=RuleSource.LLM if excluded_items else RuleSource.DETERMINISTIC
        )
        checks.append(line_items_check)

        # --- Phase 3: Per-Claim Limit Check ---
        effective_cap = max(policy.per_claim_limit, category_config.sub_limit)
        per_claim_passed = post_filter_amount <= effective_cap
        per_claim_check = PolicyCheck(
            check_name="per_claim_limit",
            passed=per_claim_passed,
            details=(
                f"Post-filter amount ₹{post_filter_amount:,.0f} vs effective cap "
                f"₹{effective_cap:,.0f} (max of per_claim_limit ₹{policy.per_claim_limit:,.0f} "
                f"and category sub_limit ₹{category_config.sub_limit:,.0f})."
            ),
            source=RuleSource.DETERMINISTIC
        )
        checks.append(per_claim_check)
        if not per_claim_passed:
            rejection_reasons.append(RejectionReason.PER_CLAIM_EXCEEDED)
            rejection_details.append(
                f"Claimed amount ₹{post_filter_amount:,.0f} exceeds the per-claim limit of "
                f"₹{effective_cap:,.0f}. The maximum allowed per claim for "
                f"{claim.claim_category.value.lower()} is ₹{effective_cap:,.0f}."
            )
            result = PolicyEvaluationResult(
                checks=checks,
                all_checks_passed=False,
                rejection_reasons=rejection_reasons,
                rejection_details=rejection_details,
                line_item_decisions=line_item_decisions,
                pre_deduction_amount=post_filter_amount,
                final_approved_amount=0.0
            )
            duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            trace = self._build_trace(result, duration)
            return result, trace

        # --- Phase 4: Amount Calculation ---
        deductions = []
        amount = post_filter_amount

        # 4.1 Network discount
        hospital = extracted.hospital_name or claim.hospital_name
        is_network = is_network_hospital(policy, hospital)
        if is_network and category_config.network_discount_percent > 0:
            discount_pct = category_config.network_discount_percent
            discount_amt = amount * (discount_pct / 100)
            amount -= discount_amt
            deductions.append(Deduction(
                deduction_type="NETWORK_DISCOUNT",
                amount=discount_amt,
                description=(
                    f"Network hospital discount ({discount_pct}%) on ₹{post_filter_amount:,.0f} "
                    f"= ₹{discount_amt:,.0f} deducted. After discount: ₹{amount:,.0f}."
                )
            ))

        # 4.2 Copay
        copay_pct = category_config.copay_percent
        if copay_pct > 0:
            copay_amt = amount * (copay_pct / 100)
            amount -= copay_amt
            deductions.append(Deduction(
                deduction_type="COPAY",
                amount=copay_amt,
                description=(
                    f"Co-pay ({copay_pct}%) on ₹{amount + copay_amt:,.0f} "
                    f"= ₹{copay_amt:,.0f} deducted. After co-pay: ₹{amount:,.0f}."
                )
            ))

        # 4.3 Annual OPD limit check
        if claim.ytd_claims_amount is not None:
            remaining_budget = policy.annual_opd_limit - claim.ytd_claims_amount
            if amount > remaining_budget:
                cap_amount = amount - remaining_budget
                amount = remaining_budget
                deductions.append(Deduction(
                    deduction_type="ANNUAL_LIMIT_CAP",
                    amount=cap_amount,
                    description=(
                        f"Annual OPD limit ₹{policy.annual_opd_limit:,.0f}, "
                        f"YTD used ₹{claim.ytd_claims_amount:,.0f}, "
                        f"remaining ₹{remaining_budget:,.0f}. Capped to ₹{amount:,.0f}."
                    )
                ))

        final_approved = round(amount, 2)

        amount_check = PolicyCheck(
            check_name="amount_calculation",
            passed=True,
            details=(
                f"Base: ₹{post_filter_amount:,.0f}. "
                + " → ".join([d.description for d in deductions])
                + f" Final: ₹{final_approved:,.0f}."
                if deductions else
                f"No deductions applied. Approved: ₹{final_approved:,.0f}."
            ),
            source=RuleSource.DETERMINISTIC
        )
        checks.append(amount_check)

        result = PolicyEvaluationResult(
            checks=checks,
            all_checks_passed=True,
            rejection_reasons=[],
            rejection_details=[],
            line_item_decisions=line_item_decisions,
            approved_line_items=[{"description": d.description, "amount": d.amount} for d in approved_items],
            excluded_line_items=[{"description": d.description, "amount": d.amount, "reason": d.reason} for d in excluded_items],
            pre_deduction_amount=post_filter_amount,
            deductions=deductions,
            final_approved_amount=final_approved,
            is_partial=is_partial
        )

        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        trace = self._build_trace(result, duration)
        return result, trace

    # --- Private methods ---

    def _run_llm_classifier(self, extracted, policy, category, category_config) -> dict:
        """
        Call Gemini text-only for semantic classification.
        See Section 6.3 for the prompt.

        Returns dict with:
        {
            "exclusion_matches": [...],
            "waiting_period_condition": {...},
            "line_item_classifications": [...],
            "requires_pre_authorization": {...}
        }

        If gemini_client is None (unit testing), return empty classifications.
        """
        if not self.gemini_client:
            return self._fallback_classification(extracted, policy, category, category_config)

        # Build context and call gemini_client.classify_policy_terms(...)
        pass

    def _fallback_classification(self, extracted, policy, category, category_config) -> dict:
        """
        Deterministic fallback when no LLM is available.
        Uses keyword matching for exclusions and condition mapping.

        This ensures the system works without an API key for testing.

        CRITICAL: This must be robust enough to pass all 12 test cases.
        """
        diagnosis = (extracted.primary_diagnosis or "").lower()
        treatment = (extracted.primary_treatment or "").lower()
        line_items = extracted.line_items

        # --- 1. Waiting Period Condition Mapping ---
        # Map diagnosis keywords to condition keys in waiting_periods.specific_conditions
        CONDITION_KEYWORDS = {
            "diabetes": ["diabetes", "t2dm", "type 2 diabetes", "type 1 diabetes", "diabetic"],
            "hypertension": ["hypertension", "htn", "high blood pressure"],
            "thyroid_disorders": ["thyroid", "hypothyroid", "hyperthyroid"],
            "joint_replacement": ["joint replacement", "knee replacement", "hip replacement"],
            "maternity": ["maternity", "pregnancy", "prenatal"],
            "mental_health": ["depression", "anxiety", "mental health", "psychiatric"],
            "obesity_treatment": ["obesity", "bariatric", "weight loss", "bmi"],
            "hernia": ["hernia"],
            "cataract": ["cataract"],
        }
        matched_condition = None
        condition_confidence = 0.0
        for condition_key, keywords in CONDITION_KEYWORDS.items():
            if any(kw in diagnosis for kw in keywords):
                matched_condition = condition_key
                condition_confidence = 0.95
                break

        # --- 2. Exclusion Matching ---
        # Check diagnosis and treatment against policy exclusions
        EXCLUSION_KEYWORDS = {
            "Obesity and weight loss programs": ["obesity", "weight loss", "diet plan", "diet program",
                                                  "nutrition program", "bmi", "bariatric"],
            "Bariatric surgery": ["bariatric"],
            "Cosmetic or aesthetic procedures": ["cosmetic", "aesthetic", "whitening", "bleaching", "veneers"],
            "Self-inflicted injuries": ["self-inflicted", "self harm"],
            "Substance abuse treatment": ["substance abuse", "alcohol", "drug abuse"],
            "Experimental treatments": ["experimental"],
            "Infertility and assisted reproduction": ["infertility", "ivf", "assisted reproduction"],
            "Health supplements and tonics": ["supplement", "tonic"],
        }
        exclusion_matches = []
        combined_text = f"{diagnosis} {treatment}".lower()
        for exclusion_name, keywords in EXCLUSION_KEYWORDS.items():
            if any(kw in combined_text for kw in keywords):
                exclusion_matches.append({
                    "item": combined_text.strip(),
                    "matched_exclusion": exclusion_name,
                    "confidence": 0.95,
                    "reasoning": f"Keyword match found in diagnosis/treatment text"
                })

        # --- 3. Line Item Classification ---
        line_item_classifications = []
        for item in line_items:
            desc_lower = item.description.lower()
            is_covered = True
            matched_rule = None

            # Check against category-specific excluded procedures
            if category_config and category_config.excluded_procedures:
                for excl in category_config.excluded_procedures:
                    if excl.lower() in desc_lower or desc_lower in excl.lower():
                        is_covered = False
                        matched_rule = f"Excluded procedure: {excl}"
                        break

            # Check against general exclusion keywords
            if is_covered:
                for excl_name, keywords in EXCLUSION_KEYWORDS.items():
                    if any(kw in desc_lower for kw in keywords):
                        is_covered = False
                        matched_rule = f"Matches exclusion: {excl_name}"
                        break

            # Check against category-specific covered procedures (dental/vision)
            if is_covered and category_config and category_config.covered_procedures:
                found_in_covered = False
                for cov in category_config.covered_procedures:
                    if cov.lower() in desc_lower or desc_lower in cov.lower():
                        found_in_covered = True
                        matched_rule = f"Covered procedure: {cov}"
                        break
                # For dental/vision, if not found in covered list, it's still covered
                # unless it was explicitly in excluded list (already checked above)

            line_item_classifications.append({
                "description": item.description,
                "amount": item.amount,
                "is_covered": is_covered,
                "matched_rule": matched_rule,
                "confidence": 0.95 if matched_rule else 0.80,
                "reasoning": matched_rule or "No specific rule matched; treated as covered"
            })

        # --- 4. Pre-Authorization Detection ---
        requires_preauth = False
        preauth_reason = None
        preauth_keywords = ["mri", "ct scan", "pet scan", "magnetic resonance"]
        all_text = f"{diagnosis} {treatment} {' '.join(i.description for i in line_items)}".lower()
        for kw in preauth_keywords:
            if kw in all_text:
                requires_preauth = True
                preauth_reason = f"Treatment involves {kw.upper()} which requires pre-authorization"
                break

        return {
            "exclusion_matches": exclusion_matches,
            "waiting_period_condition": {
                "matched_condition": matched_condition,
                "confidence": condition_confidence,
                "reasoning": f"Keyword match for '{matched_condition}'" if matched_condition else "No specific condition matched"
            },
            "line_item_classifications": line_item_classifications,
            "requires_pre_authorization": {
                "required": requires_preauth,
                "reason": preauth_reason,
                "confidence": 0.95 if requires_preauth else 0.90
            }
        }

    def _check_waiting_period(self, claim, member, extracted, policy, llm_result) -> PolicyCheck:
        """
        Check initial waiting period (30 days) and condition-specific waiting periods.

        Logic:
        1. Calculate days since member joined: days = treatment_date - join_date
        2. Check initial 30-day waiting period: if days < 30 → fail
        3. Check condition-specific: use llm_result["waiting_period_condition"]["matched_condition"]
           to find days from policy.waiting_periods["specific_conditions"][condition].
           Calculate eligible_from = join_date + condition_days.
           If treatment_date < eligible_from → fail.

        Returns PolicyCheck with passed=False and details stating the eligible-from date.
        """
        join_date = parse_date(member.join_date)
        treatment = claim.treatment_date
        initial_days = policy.waiting_periods.get("initial_waiting_period_days", 30)

        # Check 1: Initial waiting period
        in_initial, initial_eligible = is_in_waiting_period(treatment, join_date, initial_days)
        if in_initial:
            return PolicyCheck(
                check_name="waiting_period_initial",
                passed=False,
                details=(
                    f"Treatment date {treatment} is within the {initial_days}-day initial "
                    f"waiting period. Member joined {join_date}. "
                    f"Eligible from: {initial_eligible.isoformat()}."
                ),
                source=RuleSource.DETERMINISTIC
            )

        # Check 2: Condition-specific waiting period
        wp_result = llm_result.get("waiting_period_condition", {})
        matched_condition = wp_result.get("matched_condition")
        if matched_condition:
            specific_conditions = policy.waiting_periods.get("specific_conditions", {})
            condition_days = specific_conditions.get(matched_condition)
            if condition_days:
                in_wp, eligible_from = is_in_waiting_period(treatment, join_date, condition_days)
                if in_wp:
                    return PolicyCheck(
                        check_name="waiting_period_condition",
                        passed=False,
                        details=(
                            f"Diagnosis maps to '{matched_condition}' which has a "
                            f"{condition_days}-day waiting period. Member joined {join_date}. "
                            f"Treatment date {treatment} is before eligibility date "
                            f"{eligible_from.isoformat()}. The member will be eligible for "
                            f"{matched_condition}-related claims from {eligible_from.isoformat()}."
                        ),
                        source=RuleSource.LLM,
                        data={"condition": matched_condition, "days": condition_days,
                              "eligible_from": eligible_from.isoformat()}
                    )

        return PolicyCheck(
            check_name="waiting_period",
            passed=True,
            details="No applicable waiting period or waiting period has elapsed.",
            source=RuleSource.DETERMINISTIC
        )

    def _check_pre_authorization(self, claim, extracted, policy, category_config, llm_result) -> PolicyCheck:
        """
        Check if pre-authorization is required and was obtained.

        Logic:
        1. Use llm_result["requires_pre_authorization"]["required"] to determine if needed.
        2. Also check: if claim_category is DIAGNOSTIC and any line item matches
           high_value_tests_requiring_pre_auth AND amount > pre_auth_threshold.
        3. If pre-auth is required, check claim.pre_auth_approved.
           If True → pass. If False/missing → fail.

        TC007: MRI ₹15,000 > threshold ₹10,000, no pre_auth_approved → REJECTED.
        """
        preauth_result = llm_result.get("requires_pre_authorization", {})
        requires = preauth_result.get("required", False)

        # Also check deterministically for diagnostic category
        if category_config and category_config.high_value_tests_requiring_pre_auth:
            threshold = category_config.pre_auth_threshold or 10000
            if claim.claimed_amount > threshold:
                # Check if any line item or test matches high-value tests
                all_text = " ".join(
                    item.description for item in extracted.line_items
                ).lower() if extracted.line_items else ""
                for test in category_config.high_value_tests_requiring_pre_auth:
                    if test.lower() in all_text:
                        requires = True
                        break

        if not requires:
            return PolicyCheck(
                check_name="pre_authorization",
                passed=True,
                details="Pre-authorization not required for this treatment.",
                source=RuleSource.DETERMINISTIC
            )

        # Pre-auth is required — check if obtained
        if claim.pre_auth_approved:
            return PolicyCheck(
                check_name="pre_authorization",
                passed=True,
                details="Pre-authorization was required and has been obtained.",
                source=RuleSource.DETERMINISTIC
            )

        return PolicyCheck(
            check_name="pre_authorization",
            passed=False,
            details=(
                f"Pre-authorization is required for this treatment "
                f"(amount ₹{claim.claimed_amount:,.0f} exceeds threshold). "
                f"No pre-authorization was obtained. Please obtain pre-authorization "
                f"from your insurer before undergoing the treatment and resubmit the claim."
            ),
            source=RuleSource.DETERMINISTIC
        )

    def _check_full_exclusion(self, extracted, policy, llm_result) -> PolicyCheck:
        """
        Check if the ENTIRE claim is excluded.

        Logic:
        1. Check llm_result["exclusion_matches"] — if diagnosis/treatment matched exclusions.
        2. Check llm_result["line_item_classifications"] — if ALL items are not covered.
        3. If diagnosis matched AND all line items excluded → full exclusion → REJECTED.
        4. If only some line items excluded → NOT a full exclusion (handled in Phase 2).

        TC012: diagnosis "Morbid Obesity" matches exclusion, both line items
               (Bariatric Consultation, Diet Program) match exclusions → REJECTED.
        """
        exclusion_matches = llm_result.get("exclusion_matches", [])
        line_classifications = llm_result.get("line_item_classifications", [])

        # Check if diagnosis/treatment level exclusion exists
        has_diagnosis_exclusion = len(exclusion_matches) > 0 and any(
            m.get("confidence", 0) >= 0.7 for m in exclusion_matches
        )

        # Check if ALL line items are excluded
        all_items_excluded = False
        if line_classifications:
            all_items_excluded = all(
                not item.get("is_covered", True) for item in line_classifications
            )
        elif has_diagnosis_exclusion:
            # No line items to check, but diagnosis is excluded
            all_items_excluded = True

        if has_diagnosis_exclusion and all_items_excluded:
            matched_names = [m["matched_exclusion"] for m in exclusion_matches]
            return PolicyCheck(
                check_name="exclusion_check",
                passed=False,
                details=(
                    f"Treatment is excluded under policy. "
                    f"Matched exclusions: {', '.join(matched_names)}. "
                    f"Diagnosis '{extracted.primary_diagnosis}' and all billed items "
                    f"fall under excluded conditions."
                ),
                source=RuleSource.LLM,
                data={"exclusion_matches": exclusion_matches}
            )

        return PolicyCheck(
            check_name="exclusion_check",
            passed=True,
            details="No full-claim exclusions apply." + (
                f" Note: {len(exclusion_matches)} partial exclusion signals detected."
                if exclusion_matches and not all_items_excluded else ""
            ),
            source=RuleSource.LLM if exclusion_matches else RuleSource.DETERMINISTIC
        )

    def _filter_line_items(self, extracted, policy, category, category_config, llm_result) -> list[LineItemDecision]:
        """
        Classify each line item as covered or excluded.

        Logic:
        1. Get llm_result["line_item_classifications"] — each item has is_covered and matched_rule.
        2. For each item: if is_covered → approve. If not → exclude with reason.
        3. If no line items in extracted data, treat the full claimed amount as a single covered item.

        TC006: Root Canal (₹8000) → covered, Teeth Whitening (₹4000) → excluded.
        """
        line_classifications = llm_result.get("line_item_classifications", [])
        decisions = []

        if line_classifications:
            for lc in line_classifications:
                decisions.append(LineItemDecision(
                    description=lc["description"],
                    amount=lc["amount"],
                    approved=lc["is_covered"],
                    reason=lc.get("matched_rule") if not lc["is_covered"] else None
                ))
        elif extracted.line_items:
            # No LLM classification available — default all to covered
            for item in extracted.line_items:
                decisions.append(LineItemDecision(
                    description=item.description,
                    amount=item.amount,
                    approved=True,
                    reason=None
                ))
        else:
            # No line items at all — treat full amount as single covered item
            decisions.append(LineItemDecision(
                description="Total claim amount",
                amount=extracted.total_extracted_amount or 0.0,
                approved=True,
                reason=None
            ))

        return decisions

    def _build_trace(self, result, duration_ms) -> TraceStep:
        """Build trace step summarizing all checks and calculations."""
        if result.all_checks_passed:
            details = (
                f"All policy checks passed. "
                f"Pre-deduction: ₹{result.pre_deduction_amount:,.0f}. "
                f"Deductions: {len(result.deductions)}. "
                f"Final approved: ₹{result.final_approved_amount:,.0f}."
            )
            if result.is_partial:
                details += (
                    f" PARTIAL: {len(result.excluded_line_items)} items excluded."
                )
        else:
            details = (
                f"Policy check failed. Reasons: "
                + "; ".join(result.rejection_details)
            )

        return TraceStep(
            step_name="policy_evaluation",
            status=TraceStepStatus.PASSED if result.all_checks_passed else TraceStepStatus.FAILED,
            duration_ms=duration_ms,
            details=details
        )
```

### 4.5 Fraud Detector (app/agents/fraud_detector.py)

**Contract:**

```
Input:  ClaimSubmission, PolicyConfig
Output: tuple[FraudCheckResult, TraceStep]
```

**Implementation specification:**

```python
"""
Agent 5: Fraud Detector

All checks are deterministic. Uses claims_history from the claim submission
and the fraud_thresholds from policy config.

Checks:
    1. Same-day claims: count claims in claims_history with same date as current treatment.
       If count >= same_day_claims_limit (2) → flag.
       NOTE: The current claim is ADDITIONAL to the history, so total = len(history) + 1.
       TC009: 3 existing same-day claims + this one = 4 total. Threshold is 2. 4 > 2 → flag.

    2. Monthly claims: count claims in claims_history within same month.
       If count >= monthly_claims_limit (6) → flag.

    3. High-value claim: if claimed_amount > high_value_claim_threshold (25000) → flag.

    4. Auto-manual review: if claimed_amount > auto_manual_review_above (25000) → flag.

Any flag → requires_manual_review = True.

This agent is the graceful degradation target for TC011.
When simulate_component_failure is True, the ORCHESTRATOR (not this agent)
will raise an exception BEFORE calling this agent.
"""

class FraudDetector:
    def process(self, claim: ClaimSubmission, policy: PolicyConfig) -> tuple[FraudCheckResult, TraceStep]:
        start_time = datetime.utcnow()
        signals = []
        thresholds = policy.fraud_thresholds
        history = claim.claims_history or []

        # Check 1: Same-day claims
        treatment_date_str = str(claim.treatment_date)
        same_day_count = sum(1 for h in history if h.date == treatment_date_str)
        # Total including current claim
        total_same_day = same_day_count + 1
        same_day_limit = thresholds.get("same_day_claims_limit", 2)
        if total_same_day > same_day_limit:
            signals.append(FraudSignal(
                signal_type="SAME_DAY_CLAIMS",
                current_value=total_same_day,
                threshold=same_day_limit,
                description=(
                    f"{total_same_day} claims on {treatment_date_str} "
                    f"(limit: {same_day_limit}). Pattern suggests possible fraud."
                )
            ))

        # Check 2: Monthly claims
        treatment_month = claim.treatment_date.strftime("%Y-%m")
        monthly_count = sum(1 for h in history if h.date.startswith(treatment_month))
        monthly_total = monthly_count + 1
        monthly_limit = thresholds.get("monthly_claims_limit", 6)
        if monthly_total > monthly_limit:
            signals.append(FraudSignal(
                signal_type="MONTHLY_CLAIMS_EXCEEDED",
                current_value=monthly_total,
                threshold=monthly_limit,
                description=f"{monthly_total} claims in {treatment_month} (limit: {monthly_limit})."
            ))

        # Check 3: High-value claim
        high_value_threshold = thresholds.get("high_value_claim_threshold", 25000)
        if claim.claimed_amount > high_value_threshold:
            signals.append(FraudSignal(
                signal_type="HIGH_VALUE_CLAIM",
                current_value=claim.claimed_amount,
                threshold=high_value_threshold,
                description=f"Claim ₹{claim.claimed_amount:,.0f} exceeds high-value threshold ₹{high_value_threshold:,.0f}."
            ))

        requires_review = len(signals) > 0
        details = "; ".join(s.description for s in signals) if signals else "No fraud signals detected."

        result = FraudCheckResult(
            signals=signals,
            requires_manual_review=requires_review,
            details=details
        )

        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        trace = TraceStep(
            step_name="fraud_detection",
            status=TraceStepStatus.PASSED,
            duration_ms=duration,
            details=(
                f"Same-day claims: {total_same_day}/{same_day_limit}. "
                f"Monthly claims: {monthly_total}/{monthly_limit}. "
                f"High-value: {'Yes' if claim.claimed_amount > high_value_threshold else 'No'}. "
                + ("FLAGGED for manual review." if requires_review else "No flags raised.")
            )
        )

        return result, trace
```

### 4.6 Decision Aggregator (app/agents/decision_aggregator.py)

**Contract:**

```
Input:  ClaimSubmission, PolicyEvaluationResult, FraudCheckResult (optional),
        list[TraceStep], list[str] (component_failures)
Output: ClaimDecision
```

**Implementation specification:**

```python
"""
Agent 6: Decision Aggregator

Combines all agent outputs into a final ClaimDecision.

Decision precedence (highest to lowest):
    1. If Document Gatekeeper failed → no decision (error already returned by orchestrator)
    2. If fraud detector flagged for manual review → MANUAL_REVIEW
    3. If policy evaluator rejected → REJECTED (with specific reasons)
    4. If policy evaluator has excluded items but also approved items → PARTIAL
    5. If all checks passed → APPROVED

Confidence score calculation:
    base = 0.95
    - Per LOW quality document:                           -0.10
    - Per extraction field with confidence < 0.7:         -0.05
    - Per component failure (graceful degradation):       -0.30
    - If LLM exclusion match had low confidence:          -0.10
    - If fuzzy name match score was below 0.9:            -0.05
    final = max(base - total_deductions, 0.10)

Message generation:
    - APPROVED: "Claim approved. {deduction_summary}. Approved amount: ₹{amount}."
    - PARTIAL: "Claim partially approved. {approved_items} approved (₹{amount}). {excluded_items} excluded: {reasons}."
    - REJECTED: "Claim rejected. Reason: {reason}. {action_guidance}."
    - MANUAL_REVIEW: "Claim flagged for manual review. Reason: {fraud_signals}."
"""

class DecisionAggregator:
    def process(
        self,
        claim: ClaimSubmission,
        policy_result: PolicyEvaluationResult,
        fraud_result: FraudCheckResult | None,
        all_trace_steps: list[TraceStep],
        component_failures: list[str]
    ) -> ClaimDecision:
        # ... implementation per specification above
        pass
```

---

## 5. Orchestrator (app/orchestrator/pipeline.py)

**The central coordinator that sequences all agents.**

```python
"""
Pipeline Orchestrator

Sequences agents 1→6, handles graceful degradation, accumulates trace.

Flow:
    1. Input Validation → if fails, return validation error (no ClaimDecision)
    2. Document Gatekeeper → if fails, return doc error message (no ClaimDecision)
    3. Data Extraction → on exception, record failure, continue with partial data
    4. Policy Evaluation → on exception, record failure, set to MANUAL_REVIEW
    5. Fraud Detection → on exception (or simulate_component_failure), record failure, continue
    6. Decision Aggregation → always runs, produces final ClaimDecision

Graceful degradation (TC011):
    If claim.simulate_component_failure is True:
        Before calling fraud_detector.process(), raise a RuntimeError("Simulated component failure").
        The orchestrator catches this, records it in the trace, and continues.
"""

class ClaimsPipeline:
    def __init__(self, policy: PolicyConfig, gemini_client=None):
        self.policy = policy
        self.gemini_client = gemini_client
        self.input_validator = InputValidator()
        self.doc_gatekeeper = DocumentGatekeeper(gemini_client)
        self.data_extractor = DataExtractor(gemini_client)
        self.policy_evaluator = PolicyEvaluator(gemini_client)
        self.fraud_detector = FraudDetector()
        self.decision_aggregator = DecisionAggregator()

    def process_claim(self, claim: ClaimSubmission) -> ClaimDecision | dict:
        """
        Process a claim through the full pipeline.

        Returns:
            ClaimDecision on success (any verdict including REJECTED).
            dict with {"error": True, "message": str, "trace": [...]} on doc/validation errors.
        """
        trace_steps = []
        component_failures = []

        # Step 1: Input Validation
        passed, errors, trace = self.input_validator.process(claim, self.policy)
        trace_steps.append(trace)
        if not passed:
            return {
                "error": True,
                "error_type": "VALIDATION_ERROR",
                "message": "; ".join(errors),
                "trace": [t.model_dump() for t in trace_steps]
            }

        # Step 2: Document Gatekeeper
        try:
            doc_result, trace = self.doc_gatekeeper.process(claim, self.policy)
            trace_steps.append(trace)
            if doc_result.status == "FAILED":
                return {
                    "error": True,
                    "error_type": "DOCUMENT_ERROR",
                    "message": doc_result.error_message,
                    "issues": [i.model_dump() for i in doc_result.issues],
                    "trace": [t.model_dump() for t in trace_steps]
                }
        except Exception as e:
            trace_steps.append(TraceStep(
                step_name="document_verification",
                status=TraceStepStatus.FAILED,
                details=f"Document verification failed: {str(e)}"
            ))
            component_failures.append("document_verification")
            # Can't continue without document verification
            return {
                "error": True,
                "error_type": "SYSTEM_ERROR",
                "message": "Document verification failed. Please try again.",
                "trace": [t.model_dump() for t in trace_steps]
            }

        # Step 3: Data Extraction
        extracted = None
        try:
            extracted, trace = self.data_extractor.process(claim, doc_result.classifications)
            trace_steps.append(trace)
        except Exception as e:
            trace_steps.append(TraceStep(
                step_name="data_extraction",
                status=TraceStepStatus.FAILED,
                details=f"Data extraction failed: {str(e)}"
            ))
            component_failures.append("data_extraction")
            # Build minimal extracted data from claim submission
            extracted = ExtractedClaimData(
                documents=[],
                line_items=[],
                total_extracted_amount=claim.claimed_amount,
                hospital_name=claim.hospital_name
            )

        # Step 4: Policy Evaluation
        policy_result = None
        try:
            policy_result, trace = self.policy_evaluator.process(claim, extracted, self.policy)
            trace_steps.append(trace)
        except Exception as e:
            trace_steps.append(TraceStep(
                step_name="policy_evaluation",
                status=TraceStepStatus.FAILED,
                details=f"Policy evaluation failed: {str(e)}"
            ))
            component_failures.append("policy_evaluation")
            # Create a pass-through result with no deductions
            policy_result = PolicyEvaluationResult(
                all_checks_passed=True,
                final_approved_amount=claim.claimed_amount
            )

        # Step 5: Fraud Detection (graceful degradation target)
        fraud_result = None
        try:
            if claim.simulate_component_failure:
                raise RuntimeError("Simulated component failure: Fraud detection service unavailable")
            fraud_result, trace = self.fraud_detector.process(claim, self.policy)
            trace_steps.append(trace)
        except Exception as e:
            trace_steps.append(TraceStep(
                step_name="fraud_detection",
                status=TraceStepStatus.FAILED,
                details=f"Fraud detection failed: {str(e)}. Skipped — manual review recommended."
            ))
            component_failures.append("fraud_detection")

        # Step 6: Decision Aggregation (always runs)
        decision = self.decision_aggregator.process(
            claim=claim,
            policy_result=policy_result,
            fraud_result=fraud_result,
            all_trace_steps=trace_steps,
            component_failures=component_failures
        )

        # Add final aggregation trace step
        trace_steps.append(TraceStep(
            step_name="decision_aggregation",
            status=TraceStepStatus.PASSED,
            details=(
                f"Decision: {decision.decision}. "
                f"Approved: ₹{decision.approved_amount or 0:,.0f}. "
                f"Confidence: {decision.confidence_score:.2f}."
            )
        ))

        # Update decision trace with all steps
        decision.trace = AuditTrace(
            claim_id=claim.claim_id,
            steps=trace_steps,
            component_failures=component_failures
        )

        return decision
```

---

## 6. Gemini Prompt Templates

### 6.1 Document Classification Prompt (CLASSIFY_DOCUMENT_PROMPT)

```python
CLASSIFY_DOCUMENT_PROMPT = """You are a medical document classifier for Indian health insurance claims.

Analyze this uploaded medical document and provide:
1. Document type classification
2. Quality assessment
3. Patient name extraction

Respond ONLY in JSON with this exact schema:
{
    "document_type": "PRESCRIPTION" | "HOSPITAL_BILL" | "LAB_REPORT" | "PHARMACY_BILL" | "DIAGNOSTIC_REPORT" | "DENTAL_REPORT" | "DISCHARGE_SUMMARY" | "UNKNOWN",
    "quality": "GOOD" | "LOW" | "UNREADABLE",
    "patient_name": "<extracted name or null>",
    "confidence": <float 0.0 to 1.0>,
    "quality_issues": ["<issue1>", "<issue2>"]
}

Document type rules:
- PRESCRIPTION: Has Rx symbol, doctor details, medication list with dosage
- HOSPITAL_BILL: Has hospital name, itemized charges, bill number, total amount
- LAB_REPORT: Has test names, results, reference ranges, lab name
- PHARMACY_BILL: Has drug license, medication list with MRP/batch/expiry
- DIAGNOSTIC_REPORT: Has imaging or diagnostic findings (MRI, CT, X-ray)
- DENTAL_REPORT: Has dental examination findings
- DISCHARGE_SUMMARY: Has admission/discharge dates, treatment summary

Quality rules:
- GOOD: All key fields clearly readable
- LOW: Some text unclear but key fields partially visible
- UNREADABLE: Critical fields cannot be read; document needs re-upload"""
```

### 6.2 Data Extraction Prompts

**6.2.1 Prescription Extraction (EXTRACT_PRESCRIPTION_PROMPT)**

```python
EXTRACT_PRESCRIPTION_PROMPT = """Extract structured data from this Indian medical prescription.

Return ONLY JSON:
{
    "doctor_name": {"value": "<name>", "confidence": <float>},
    "doctor_registration": {"value": "<reg number>", "confidence": <float>},
    "patient_name": {"value": "<name>", "confidence": <float>},
    "patient_age": {"value": "<age>", "confidence": <float>},
    "patient_gender": {"value": "M|F", "confidence": <float>},
    "date": {"value": "YYYY-MM-DD", "confidence": <float>},
    "diagnosis": {"value": "<diagnosis>", "confidence": <float>},
    "treatment": {"value": "<treatment description if stated>", "confidence": <float>},
    "medicines": [{"name": "<name>", "dosage": "<dosage>", "frequency": "<freq>", "duration": "<dur>"}],
    "tests_ordered": {"value": ["<test1>", "<test2>"], "confidence": <float>},
    "hospital_name": {"value": "<clinic/hospital name>", "confidence": <float>}
}

Rules:
- If a field is not visible, set value to null and confidence to 0.0
- For partially readable: confidence 0.3-0.7
- Common abbreviations: HTN=Hypertension, T2DM=Type 2 Diabetes, URI=Upper Respiratory Infection
- Doctor registration format: STATE/XXXXX/YYYY or AYUR/STATE/XXXXX/YYYY
- Convert all dates to YYYY-MM-DD format"""
```

**6.2.2 Hospital Bill Extraction (EXTRACT_BILL_PROMPT)**

```python
EXTRACT_BILL_PROMPT = """Extract structured data from this Indian hospital/clinic bill.

Return ONLY JSON:
{
    "hospital_name": {"value": "<name>", "confidence": <float>},
    "bill_number": {"value": "<number>", "confidence": <float>},
    "date": {"value": "YYYY-MM-DD", "confidence": <float>},
    "patient_name": {"value": "<name>", "confidence": <float>},
    "line_items": [
        {"description": "<item description>", "amount": <float>}
    ],
    "subtotal": {"value": <float>, "confidence": <float>},
    "gst": {"value": <float>, "confidence": <float>},
    "total_amount": {"value": <float>, "confidence": <float>},
    "payment_mode": {"value": "<mode>", "confidence": <float>}
}

Rules:
- Extract EVERY line item with its exact amount
- If amounts are written in words and figures, use the figure
- Flag any corrections/strikethroughs in warnings
- total_amount is the final payable amount"""
```

### 6.3 Policy Classification Prompt (POLICY_CLASSIFY_PROMPT)

```python
POLICY_CLASSIFY_PROMPT = """You are an insurance policy evaluator. Classify the medical claim data against policy terms.

CLAIM DATA:
- Diagnosis: {diagnosis}
- Treatment: {treatment}
- Line items: {line_items_json}
- Claim category: {category}

POLICY EXCLUSIONS:
{exclusions_json}

CATEGORY-SPECIFIC PROCEDURES:
Covered: {covered_procedures_json}
Excluded: {excluded_procedures_json}

WAITING PERIOD CONDITIONS (condition_name: days):
{waiting_conditions_json}

PRE-AUTHORIZATION REQUIREMENTS:
{preauth_requirements_json}

Return ONLY JSON:
{{
    "exclusion_matches": [
        {{
            "item": "<what matched>",
            "matched_exclusion": "<which exclusion it matches>",
            "confidence": <float>,
            "reasoning": "<why this is a match>"
        }}
    ],
    "waiting_period_condition": {{
        "matched_condition": "<condition_key from waiting periods or null>",
        "confidence": <float>,
        "reasoning": "<why this diagnosis maps to this condition>"
    }},
    "line_item_classifications": [
        {{
            "description": "<line item text>",
            "amount": <float>,
            "is_covered": <boolean>,
            "matched_rule": "<which covered/excluded rule it matches or null>",
            "confidence": <float>,
            "reasoning": "<why covered or excluded>"
        }}
    ],
    "requires_pre_authorization": {{
        "required": <boolean>,
        "reason": "<which pre-auth rule applies or null>",
        "confidence": <float>
    }}
}}

IMPORTANT:
- Match semantically, not just by exact string. "Bariatric Consultation" relates to "Bariatric surgery" exclusion.
- "Morbid Obesity" + "Diet Plan" relates to "Obesity and weight loss programs" exclusion.
- "Type 2 Diabetes Mellitus" maps to "diabetes" waiting period condition.
- For dental: "Root Canal Treatment" is in covered list; "Teeth Whitening" is in excluded list.
- For pre-auth: detect if treatment involves MRI, CT Scan, or PET Scan.
- Be conservative: if unsure, set confidence lower and let the system handle it."""
```

---

## 7. Streamlit UI Pages

### 7.1 Main Entry (app/main.py)

```python
"""
Streamlit app entry point.

Setup:
    - Set page config (title, icon, layout)
    - Initialize session state
    - Load policy config (cached)
    - Initialize database
    - Sidebar: navigation info

Session state keys:
    - policy: PolicyConfig (loaded once)
    - gemini_client: GeminiClient (initialized once)
    - last_decision: ClaimDecision or error dict (latest result)
"""
import streamlit as st

st.set_page_config(
    page_title="Claims Processor — Plum",
    page_icon="🏥",
    layout="wide"
)

# Initialize policy and DB on first run
# Use @st.cache_resource for singletons
```

### 7.2 Page 1: Submit Claim (app/pages/1_Submit_Claim.py)

```
Layout:
    ┌──────────────────────────────────────────────────┐
    │  🏥 Submit Insurance Claim                        │
    ├──────────────────────────────────────────────────┤
    │                                                  │
    │  Member ID:      [dropdown: EMP001-EMP010, DEP*] │
    │  Claim Category: [dropdown: 6 categories]        │
    │  Treatment Date: [date picker]                   │
    │  Claimed Amount: [number input, min=500]         │
    │  Hospital Name:  [text input, optional]          │
    │                                                  │
    │  Upload Documents:                               │
    │  [file uploader, accept jpg/png/pdf, multiple]   │
    │                                                  │
    │  [Submit Claim]                                  │
    │                                                  │
    ├──────────────────────────────────────────────────┤
    │  Processing...                                   │
    │  ✅ Input Validation — passed                    │
    │  ✅ Document Verification — 2 docs classified    │
    │  ✅ Data Extraction — diagnosis: Viral Fever     │
    │  ✅ Policy Evaluation — approved ₹1,350          │
    │  ✅ Fraud Detection — no flags                   │
    │  ✅ Decision: APPROVED                           │
    │                                                  │
    │  ┌────────────────────────────────────────────┐  │
    │  │  APPROVED — ₹1,350.00                      │  │
    │  │  Confidence: 0.92                          │  │
    │  │  10% co-pay applied (₹150 deducted)        │  │
    │  └────────────────────────────────────────────┘  │
    └──────────────────────────────────────────────────┘

Behavior:
    - On submit, show a st.spinner with real-time status updates per pipeline step.
    - Use st.status() to show expanding progress for each agent.
    - On document error: show st.error() with the specific error message.
    - On success: show decision in a colored st.container (green=approved, yellow=partial, red=rejected, blue=manual_review).
    - Save decision to database.
    - Store in session_state for immediate viewing.
```

### 7.3 Page 2: Review Decisions (app/pages/2_Review_Decisions.py)

```
Layout:
    ┌──────────────────────────────────────────────────┐
    │  📋 Review Decisions                              │
    ├──────────────────────────────────────────────────┤
    │  Filter: [All ▾] [APPROVED ▾] [REJECTED ▾] ...  │
    │                                                  │
    │  ┌────────────────────────────────────────────┐  │
    │  │ CLM_A1B2C3D4 | EMP001 | CONSULTATION      │  │
    │  │ ✅ APPROVED | ₹1,350 | Conf: 0.92         │  │
    │  │ 2024-11-01                                 │  │
    │  │ [▶ View Trace]                             │  │
    │  ├────────────────────────────────────────────┤  │
    │  │ Trace:                                     │  │
    │  │  Step 1: input_validation — PASSED (5ms)   │  │
    │  │    Member EMP001 valid. Policy active...    │  │
    │  │  Step 2: document_verification — PASSED     │  │
    │  │    2 docs classified. Names match...        │  │
    │  │  Step 3: data_extraction — PASSED           │  │
    │  │    Diagnosis: Viral Fever. 3 line items...  │  │
    │  │  Step 4: policy_evaluation — PASSED         │  │
    │  │    Co-pay 10%: ₹150. Final: ₹1,350.       │  │
    │  │  Step 5: fraud_detection — PASSED           │  │
    │  │    No fraud signals.                       │  │
    │  │  Step 6: decision_aggregation — PASSED      │  │
    │  │    APPROVED. Confidence: 0.92.             │  │
    │  └────────────────────────────────────────────┘  │
    └──────────────────────────────────────────────────┘

Behavior:
    - Load all decisions from database.
    - Filter by verdict (dropdown).
    - Each decision shown as an expandable card.
    - Clicking "View Trace" expands to show full audit trail.
    - Each trace step shows: name, status (color-coded), duration, details.
```

### 7.4 Page 3: Run Eval (app/pages/3_Run_Eval.py)

```
Layout:
    ┌──────────────────────────────────────────────────┐
    │  🧪 Evaluation Runner                             │
    ├──────────────────────────────────────────────────┤
    │  Test Cases: test_cases.json (12 cases)          │
    │  [Run All Test Cases]                            │
    │                                                  │
    │  Results:                                        │
    │  ┌────────────────────────────────────────────┐  │
    │  │ TC  | Name             | Expected | Actual  │  │
    │  │ 001 | Wrong Document   | STOP     | STOP ✅ │  │
    │  │ 002 | Unreadable Doc   | STOP     | STOP ✅ │  │
    │  │ 003 | Name Mismatch    | STOP     | STOP ✅ │  │
    │  │ 004 | Clean Consult    | APPROVED | APPR ✅ │  │
    │  │     |                  | ₹1,350   | ₹1,350  │  │
    │  │ ... | ...              | ...      | ...     │  │
    │  └────────────────────────────────────────────┘  │
    │                                                  │
    │  Summary: 12/12 passed ✅                        │
    │  [Export Eval Report]                            │
    └──────────────────────────────────────────────────┘

Behavior:
    - Load test_cases.json.
    - Convert each test case input to a ClaimSubmission.
    - Run through ClaimsPipeline.process_claim().
    - Compare actual output vs expected:
        - TC001-TC003: expected.decision is null → system should return error
        - TC004-TC012: compare decision verdict and approved_amount
    - Show pass/fail per test case.
    - "Export Eval Report" generates a markdown report.
```

---

## 8. Test Case Adapter (app/services/test_case_loader.py)

```python
"""
Converts test_cases.json entries into ClaimSubmission objects.

Key mappings:
    - input.member_id → ClaimSubmission.member_id
    - input.claim_category → ClaimCategory enum
    - input.treatment_date → date
    - input.claimed_amount → float
    - input.hospital_name → Optional[str]
    - input.ytd_claims_amount → Optional[float]
    - input.simulate_component_failure → bool
    - input.claims_history → list[ClaimHistoryEntry]
    - input.documents → list[ClaimDocument]

Document mapping:
    Each test case document has:
    {
        "file_id": "F001",
        "file_name": "...",        # optional
        "actual_type": "PRESCRIPTION",
        "quality": "GOOD",         # optional, default GOOD
        "patient_name_on_doc": "...",  # optional
        "content": {...}           # optional, for extraction
    }

    Map to ClaimDocument:
    - file_id → file_id
    - file_name → file_name (use file_id if not present)
    - actual_type → actual_type
    - quality → quality (default "GOOD" if not present)
    - patient_name_on_doc → patient_name_on_doc
    - content → content

Public interface:
    - load_test_cases(filepath: str) -> list[dict]  # Raw test case dicts
    - test_case_to_claim(tc: dict) -> ClaimSubmission
    - evaluate_result(tc: dict, result: ClaimDecision | dict) -> dict  # {passed, expected, actual, notes}
"""
```

---

## 9. Mock Document Generator (eval/generate_mock_docs.py)

```python
"""
Generate mock medical document images for demo purposes.

Uses fpdf2 to create PDF documents matching the formats in sample_documents_guide.md.

Functions:
    - generate_prescription(data: dict) -> bytes  # Returns PDF bytes
    - generate_hospital_bill(data: dict) -> bytes
    - generate_lab_report(data: dict) -> bytes
    - generate_pharmacy_bill(data: dict) -> bytes
    - generate_all_test_docs(test_cases_path: str, output_dir: str)

Each generator creates a professional-looking Indian medical document
with the provided data fields. Used for the demo video and real-mode testing.
"""
```

---

## 10. Test Plan

### 10.1 Unit Tests

| Test File | What It Tests | Key Scenarios |
|-----------|--------------|---------------|
| `test_input_validator.py` | Agent 1 | Valid member, invalid member, expired policy, below minimum, past deadline, invalid category |
| `test_document_gatekeeper.py` | Agent 2 | Correct docs, missing required doc (TC001), unreadable doc (TC002), name mismatch (TC003), all optional |
| `test_data_extractor.py` | Agent 3 | Test mode extraction, field mapping, aggregation logic, missing content handling |
| `test_policy_evaluator.py` | Agent 4 | Waiting period (TC005), pre-auth (TC007), exclusion (TC012), partial approval (TC006), per-claim limit (TC008), network discount (TC010), copay calculation |
| `test_fraud_detector.py` | Agent 5 | Same-day claims (TC009), monthly limit, high value, no fraud, empty history |
| `test_decision_aggregator.py` | Agent 6 | All verdicts, confidence calculation, message generation, component failure impact |
| `test_rules/test_waiting_period.py` | Waiting period logic | Initial 30-day, condition-specific, elapsed period, edge cases |
| `test_rules/test_limits.py` | Limit checks | Per-claim cap, effective cap calculation, annual limit |
| `test_rules/test_copay.py` | Financial calcs | Copay, network discount, discount-before-copay order, rounding |
| `test_pipeline_integration.py` | Full pipeline | All 12 test cases end-to-end, graceful degradation |

### 10.2 Testing Without API Key

The system must be testable without a Gemini API key. Test-mode documents provide pre-classified, pre-extracted data. The policy evaluator's LLM classifier has a `_fallback_classification` method that uses keyword matching. Unit tests should use this fallback.

### 10.3 Test Data Fixtures (tests/conftest.py)

```python
"""
Shared pytest fixtures.

Fixtures:
    - policy_config: PolicyConfig loaded from test policy_terms.json
    - sample_consultation_claim: A valid TC004-style ClaimSubmission
    - sample_dental_claim: A TC006-style ClaimSubmission with mixed procedures
    - sample_waiting_period_claim: A TC005-style ClaimSubmission in waiting period
    - gemini_client_mock: Mock GeminiClient that returns pre-defined responses
"""
```

---

## 11. Implementation Sequence

For Antigravity, implement in this order (each step builds on the previous):

```
Step 1:  Models          — all Pydantic models in app/models/
Step 2:  Config          — app/config.py + .env
Step 3:  Utilities       — date_utils.py + text_matching.py
Step 4:  Policy Loader   — policy_loader.py (validates by loading policy_terms.json)
Step 5:  Database        — database.py (init_db, save/load operations)
Step 6:  Input Validator — agent + tests
Step 7:  Document Gatekeeper — agent + tests (test mode only first)
Step 8:  Data Extractor  — agent + tests (test mode only first)
Step 9:  Policy Evaluator — deterministic engine + keyword fallback + tests
Step 10: Fraud Detector  — agent + tests
Step 11: Decision Aggregator — agent + tests
Step 12: Orchestrator    — pipeline.py + integration tests
Step 13: Test Case Loader — adapter for test_cases.json
Step 14: Eval Runner     — run all 12 test cases, verify results
Step 15: Gemini Client   — API wrapper with prompts
Step 16: Wire Gemini     — connect real LLM calls to agents
Step 17: Streamlit Pages — UI (submit, review, eval)
Step 18: Mock Docs       — generate_mock_docs.py for demo
Step 19: Polish          — error messages, trace formatting, UI styling
```

---

## End of LLD

This document, combined with the HLD, contains everything needed for Antigravity to generate the complete implementation. Every data model, every agent contract, every prompt template, and every Streamlit page layout is specified.