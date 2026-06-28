# High-Level Design: Health Insurance Claims Processing System

## Document Version

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Date | 2026-06-25 |
| Status | Final — ready for implementation |
| Target IDE | Antigravity |
| Source Assignment | Plum AI Engineer Assignment |

---

## 1. System Context and Purpose

### 1.1 What This System Does

This system automates the processing of OPD (outpatient) health insurance claims for a group health insurance policy. Today, a human reviewer examines uploaded medical documents (prescriptions, bills, lab reports) against policy rules to decide whether to approve, partially approve, or reject each claim. This system replaces that manual step with an automated multi-agent pipeline.

### 1.2 Core Behaviours (Non-Negotiable)

1. Accept a claim submission (member details, treatment type, amount, uploaded documents).
2. Catch document problems early — wrong document type, unreadable documents, cross-document patient name mismatches — and return specific, actionable error messages before any processing.
3. Extract structured data from uploaded medical documents (handle messy inputs: handwritten prescriptions, phone photos, rubber stamps).
4. Make a claim decision: `APPROVED`, `PARTIAL`, `REJECTED`, or `MANUAL_REVIEW`.
5. Make every decision explainable — full audit trace showing what was checked, what passed, what failed, and why.
6. Handle component failures gracefully — no crashes, continue with degraded confidence.

### 1.3 Scale Context

- Current: 12 test cases for evaluation; real-world target is 75,000+ claims/year.
- Future: path to 10 million lives by 2030.
- This implementation targets the evaluation scope. The architecture document describes the scale-out path.

---

## 2. Architecture Pattern: Multi-Agent Pipeline

### 2.1 Why Multi-Agent

The assignment offers bonus points for multi-agent architecture, but the choice is also structurally sound. Each stage of claims processing has a distinct responsibility, distinct failure modes, and distinct input/output contracts. Separating them into agents gives us:

- **Independent testability** — each agent can be unit-tested against its contract without running the full pipeline.
- **Graceful degradation** — if one agent fails (e.g., LLM timeout during extraction), the orchestrator can skip it, reduce confidence, and continue.
- **Clear observability** — each agent writes a trace step, making the audit trail a natural byproduct.
- **Independent scaling** — at 10x load, the document extraction agent (GPU-bound) and the policy evaluator (CPU-bound) can scale independently.

### 2.2 Agent Inventory

| # | Agent | Type | Uses LLM? | Purpose |
|---|-------|------|-----------|---------|
| 1 | Input Validator | Deterministic | No | Validates member, policy, dates, minimum amounts |
| 2 | Document Gatekeeper | LLM (Gemini Vision) | Yes | Classifies doc types, checks quality, cross-doc consistency |
| 3 | Data Extractor | LLM (Gemini Vision) | Yes | Extracts structured JSON from medical documents |
| 4 | Policy Evaluator | Hybrid | Partial | Deterministic rules + LLM for semantic matching |
| 5 | Fraud Detector | Deterministic | No | Pattern checks on claims history |
| 6 | Decision Aggregator | Deterministic | No | Combines all signals into verdict + trace |

### 2.3 Orchestrator

The orchestrator is not an agent — it is the pipeline coordinator. It:

- Sequences agents in order (1 → 2 → 3 → 4 → 5 → 6).
- Stops the pipeline early if the Document Gatekeeper returns a blocking issue.
- Wraps each agent call in a try/catch for graceful degradation.
- Accumulates trace steps from each agent into the final audit trail.
- Passes output of each agent as input to the next.

---

## 3. Technology Stack

### 3.1 Stack Selection

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Language | Python 3.11+ | AI/ML ecosystem, async support, Gemini SDK |
| Web Framework | Streamlit | Fastest to build; native file upload; multi-page; sufficient for demo |
| LLM Provider | Google Gemini Flash (gemini-2.0-flash) | Cheapest vision model; strong structured extraction; $0.10/1M input tokens |
| Database | SQLite | Zero cost, zero infra, sufficient for evaluation scope |
| Deployment | Streamlit Community Cloud or Render (free tier) | Zero cost hosting |
| Testing | pytest | Standard Python testing |

### 3.2 Cost Estimate

| Component | Weekly Cost |
|-----------|-------------|
| Gemini Flash API (vision calls, ~50 claims/week during dev) | ₹5–10 (~$0.06–0.12) |
| Streamlit Cloud hosting | Free |
| SQLite | Free |
| **Total** | **< ₹15/week during development** |

At production scale (100 claims/day), Gemini API cost would be ~₹120/week ($1.40) — still under the ₹1,250/week budget.

### 3.3 Rejected Alternatives

| Option | Rejected Because |
|--------|-----------------|
| AWS Bedrock (Claude) | 10-20x more expensive per vision call than Gemini Flash for this use case |
| React/Next.js frontend | 2-3x more build time for no evaluation benefit; Streamlit is sufficient |
| PostgreSQL/DynamoDB | Overkill for 12 test cases; adds deployment complexity and cost |
| AWS Lambda | Adds cold start latency and deployment complexity; no benefit at this scale |
| OpenAI GPT-4o-mini | Comparable cost to Gemini Flash but Gemini has stronger structured output via JSON mode |

---

## 4. End-to-End Data Flow

### 4.1 Happy Path (Full Approval)

```
Member submits claim via Streamlit UI
    ├── member_id, claim_category, treatment_date, claimed_amount, documents[]
    │
    ▼
[Input Validator]
    ├── Member exists in policy? ✓
    ├── Policy active on treatment date? ✓
    ├── Amount ≥ ₹500 minimum? ✓
    ├── Within 30-day submission deadline? ✓
    │
    ▼
[Document Gatekeeper] ← Gemini Vision
    ├── Classify each uploaded document → type (PRESCRIPTION, HOSPITAL_BILL, etc.)
    ├── Check quality → GOOD / LOW / UNREADABLE
    ├── Required docs present for claim category? ✓
    ├── Cross-doc patient name match? ✓
    │
    ▼
[Data Extractor] ← Gemini Vision
    ├── Extract structured JSON from each document
    ├── Prescription → {doctor, registration, patient, diagnosis, medicines, date}
    ├── Hospital Bill → {hospital, patient, line_items[], total, date}
    ├── Lab Report → {lab, patient, tests[], results[], date}
    │
    ▼
[Policy Evaluator] ← Hybrid (deterministic + Gemini text)
    ├── Deterministic: waiting period check (date math)
    ├── Deterministic: per-claim limit check
    ├── Deterministic: pre-authorization check
    ├── LLM: diagnosis → exclusion matching
    ├── LLM: line items → covered/excluded procedure matching
    ├── Deterministic: network discount calculation
    ├── Deterministic: copay calculation
    ├── Deterministic: annual limit check
    │
    ▼
[Fraud Detector]
    ├── Same-day claims count check
    ├── Monthly claims limit check
    ├── High-value threshold check
    │
    ▼
[Decision Aggregator]
    ├── Combine all signals
    ├── Calculate confidence score
    ├── Determine verdict: APPROVED / PARTIAL / REJECTED / MANUAL_REVIEW
    ├── Build full audit trace
    │
    ▼
Decision displayed in Streamlit UI with full trace
```

### 4.2 Early Stop Path (Document Problem)

```
Member submits claim
    ▼
[Input Validator] ✓
    ▼
[Document Gatekeeper]
    ├── Missing required document → STOP
    │   └── "You uploaded 2 prescriptions but we need a hospital bill.
    │       Please upload your hospital bill/clinic invoice for this consultation."
    │
    ├── Unreadable document → STOP
    │   └── "Your pharmacy bill (blurry_bill.jpg) is not readable.
    │       Please re-upload a clearer photo of your pharmacy bill."
    │
    ├── Patient name mismatch → STOP
    │   └── "The prescription is for 'Rajesh Kumar' but the hospital bill
    │       is for 'Arjun Mehta'. All documents must be for the same patient."
    │
    ▼
NO further processing. Return error with specific, actionable message.
```

### 4.3 Graceful Degradation Path

```
Member submits claim
    ▼
[Input Validator] ✓
[Document Gatekeeper] ✓
[Data Extractor] ← FAILS (LLM timeout)
    │
    ├── Orchestrator catches the exception
    ├── Records TraceStep with status: FAILED
    ├── Continues pipeline with partial data
    │
    ▼
[Policy Evaluator] runs with available data, skips checks needing missing fields
[Fraud Detector] ✓
[Decision Aggregator]
    ├── Confidence score reduced (e.g., 0.85 → 0.55)
    ├── Adds note: "Data extraction failed; manual review recommended"
    ├── Decision may still be APPROVED if enough data was available
    │
    ▼
Decision output includes component failure in trace
```

---

## 5. Component Overview

### 5.1 Input Validator

**Responsibility:** Validate the claim submission metadata before any AI processing.

**Checks (all deterministic):**

1. `member_id` exists in `policy_terms.json` members list.
2. Policy is active on the treatment date (between `policy_start_date` and `policy_end_date`).
3. `claimed_amount` ≥ `submission_rules.minimum_claim_amount` (₹500).
4. `treatment_date` is within `submission_rules.deadline_days_from_treatment` (30 days) of submission.
5. `claim_category` is a valid category from `opd_categories`.

**On failure:** Returns a specific validation error. Does not proceed to Document Gatekeeper.

### 5.2 Document Gatekeeper Agent

**Responsibility:** Verify uploaded documents are correct, readable, and consistent before extraction.

**Uses LLM:** Yes — Gemini Vision for document classification and quality assessment.

**Three-step process:**

1. **Document Classification** — For each uploaded file, use Gemini Vision to classify it as one of: `PRESCRIPTION`, `HOSPITAL_BILL`, `LAB_REPORT`, `PHARMACY_BILL`, `DIAGNOSTIC_REPORT`, `DENTAL_REPORT`, `DISCHARGE_SUMMARY`. Compare against `document_requirements[claim_category].required` and `optional` lists.

2. **Quality Assessment** — For each document, assess readability: `GOOD`, `LOW`, `UNREADABLE`. If any required document is `UNREADABLE`, stop and ask for re-upload of that specific document.

3. **Cross-Document Consistency** — Extract patient name from each document and check they all match. Use fuzzy string matching (not exact match) to handle minor variations (e.g., "Rajesh Kumar" vs "R. Kumar"). If names are clearly different people, stop with specific error naming both patients.

**On failure:** Returns a blocking error with specific, actionable message. Pipeline stops. No claim decision is produced.

**Single LLM call strategy:** Combine classification + quality + patient name extraction into one Gemini Vision call per document to minimize API calls and cost.

### 5.3 Data Extraction Agent

**Responsibility:** Extract structured data from medical documents into standardized JSON.

**Uses LLM:** Yes — Gemini Vision with structured output prompts.

**Extraction schemas by document type:**

- **Prescription:** doctor_name, doctor_registration, patient_name, patient_age, patient_gender, date, diagnosis, medicines (list with name, dosage, frequency, duration), tests_ordered, hospital_name.
- **Hospital Bill:** hospital_name, bill_number, date, patient_name, line_items (list with description, amount), subtotal, gst, total, payment_mode.
- **Lab Report:** lab_name, patient_name, referring_doctor, sample_date, report_date, tests (list with name, result, unit, normal_range), pathologist_name, remarks.
- **Pharmacy Bill:** pharmacy_name, bill_number, date, patient_name, prescribing_doctor, medicines (list with name, batch, expiry, quantity, mrp, amount), net_amount.

**Confidence scoring:** Each extracted field gets a confidence score (0.0–1.0). Fields obscured by stamps, handwriting, or poor quality get lower confidence. The overall document confidence is the minimum of required field confidences.

**Structured output:** Use Gemini's JSON mode to enforce schema compliance. If a field cannot be extracted, it is set to `null` with confidence `0.0` and a warning string explaining why.

### 5.4 Policy Evaluator (Hybrid)

**Responsibility:** Apply policy rules to extracted data and determine eligibility, deductions, and approved amount.

**Hybrid approach:** Two sub-components run in sequence.

#### 5.4.1 LLM Classifier (runs first)

Uses Gemini Flash (text-only, not vision) for semantic matching tasks that deterministic code cannot handle reliably:

1. **Diagnosis → Condition Mapping:** Map extracted diagnosis text to the conditions in `waiting_periods.specific_conditions`. Example: "Type 2 Diabetes Mellitus" → `diabetes` (90-day waiting period).

2. **Diagnosis/Treatment → Exclusion Matching:** Check if the diagnosis or treatment matches any item in `exclusions.conditions`, `exclusions.dental_exclusions`, or `exclusions.vision_exclusions`. Example: "Morbid Obesity — BMI 37" + "Bariatric Consultation" → matches "Obesity and weight loss programs" and "Bariatric surgery".

3. **Line Item → Procedure Coverage Matching (dental/vision):** For dental claims, check each line item against `opd_categories.dental.covered_procedures` and `excluded_procedures`. For vision claims, check against `covered_items` and `excluded_items`. Example: "Root Canal Treatment" → covered; "Teeth Whitening" → excluded.

4. **Pre-Authorization Detection:** Determine if the treatment involves MRI, CT Scan, or PET Scan (from `pre_authorization.required_for`).

**Output:** Structured classifications that feed into the deterministic engine.

#### 5.4.2 Deterministic Engine (runs second)

Pure code — no LLM. Uses the LLM classifier's output plus extracted data:

**The Calculation Waterfall** (exact order — must be implemented as specified):

**Phase 1 — Hard Rejection Gates (any fail → REJECT, pipeline continues to aggregator):**

| # | Check | Logic | Rejection Reason |
|---|-------|-------|-----------------|
| 1 | Waiting Period | If LLM mapped diagnosis to a specific condition, calculate: `member.join_date` + `condition_waiting_days`. If `treatment_date` < eligibility date → reject. Also check initial 30-day waiting period. | `WAITING_PERIOD` |
| 2 | Pre-Authorization | If LLM detected MRI/CT/PET and amount exceeds threshold (₹10,000 for MRI/CT), check if pre-auth was provided. If not → reject. | `PRE_AUTH_MISSING` |
| 3 | Exclusion (full claim) | If LLM determined ALL line items or the overall diagnosis/treatment are excluded → reject. | `EXCLUDED_CONDITION` |

**Phase 2 — Line-Item Filtering (can produce PARTIAL):**

For each line item in the bill:
- If LLM classified it as an excluded procedure → remove it, record reason.
- Sum remaining approved line items = `post_filter_amount`.
- If all items removed → already caught in Phase 1 (EXCLUDED_CONDITION).
- If some items removed → flag for PARTIAL decision.

**Phase 3 — Per-Claim Limit Check (on post-filtered amount):**

```
effective_per_claim_cap = max(per_claim_limit, category_sub_limit)

For CONSULTATION: max(5000, 2000) = ₹5,000
For DENTAL:       max(5000, 10000) = ₹10,000
For DIAGNOSTIC:   max(5000, 10000) = ₹10,000
For PHARMACY:     max(5000, 15000) = ₹15,000
For VISION:       max(5000, 5000) = ₹5,000
For ALT_MEDICINE: max(5000, 8000) = ₹8,000

If post_filter_amount > effective_per_claim_cap → REJECTED (PER_CLAIM_EXCEEDED)
```

**Phase 4 — Amount Calculation (on approved items):**

```
Step 1: Start with post_filter_amount (sum of approved line items)

Step 2: Apply network discount (if applicable)
        If hospital_name matches any entry in network_hospitals:
            discounted = post_filter_amount × (1 - network_discount_percent / 100)
        Else:
            discounted = post_filter_amount

Step 3: Apply copay
        copay_amount = discounted × (copay_percent / 100)
        after_copay = discounted - copay_amount

        Special case for pharmacy:
        If category == PHARMACY and drug is branded (not generic):
            copay_amount = discounted × (branded_drug_copay_percent / 100)

Step 4: Check against annual category sub-limit (if YTD per-category data available)
        remaining_category_budget = category_sub_limit - ytd_category_amount
        after_sublimit = min(after_copay, remaining_category_budget)
        NOTE: If per-category YTD is not provided, skip this check.

Step 5: Check against annual OPD limit
        remaining_opd_budget = annual_opd_limit - ytd_claims_amount
        final_approved = min(after_copay, remaining_opd_budget)
        NOTE: If ytd_claims_amount is not provided, skip this check.

Step 6: final_approved_amount = final_approved (rounded to 2 decimal places)
```

### 5.5 Fraud Detector

**Responsibility:** Check for fraud patterns in claims history. Pure deterministic.

**Checks:**

| Check | Threshold | Action |
|-------|-----------|--------|
| Same-day claims | > `fraud_thresholds.same_day_claims_limit` (2) | Flag → MANUAL_REVIEW |
| Monthly claims | > `fraud_thresholds.monthly_claims_limit` (6) | Flag → MANUAL_REVIEW |
| High-value claim | > `fraud_thresholds.high_value_claim_threshold` (₹25,000) | Flag → MANUAL_REVIEW |
| Auto-manual review | > `fraud_thresholds.auto_manual_review_above` (₹25,000) | Flag → MANUAL_REVIEW |

**Note:** Fraud signals route to `MANUAL_REVIEW`, never to auto-rejection. This is a deliberate design choice — fraud detection has false positives, and auto-rejection on suspicion is a poor user experience.

**Input:** The `claims_history` field from the claim submission (if provided), plus any claims already stored in the local database.

### 5.6 Decision Aggregator

**Responsibility:** Combine all agent outputs into a single claim decision with full audit trace.

**Decision logic:**

```
If any agent returned a blocking error (doc gatekeeper):
    → No decision (return error)

If fraud detector flagged for manual review:
    → MANUAL_REVIEW

If policy evaluator rejected (waiting period, pre-auth, exclusion, per-claim limit):
    → REJECTED with specific reason(s)

If some line items were excluded but others approved:
    → PARTIAL with approved_amount from calculation

If all checks passed:
    → APPROVED with approved_amount from calculation
```

**Confidence score calculation:**

```
base_confidence = 0.95

Deductions:
- For each LOW quality document:        -0.10
- For each extraction field with confidence < 0.7:  -0.05
- If any component failed (graceful degradation):   -0.30
- If LLM exclusion match confidence is low:         -0.10
- If fuzzy name match score < 0.9:                  -0.05

final_confidence = max(base_confidence - total_deductions, 0.10)

If final_confidence < fraud_score_manual_review_threshold (0.80):
    → Consider routing to MANUAL_REVIEW
```

**Audit trace structure:**

Every decision includes a complete trace with one entry per pipeline step:

```
{
    "claim_id": "CLM_XXXX",
    "timestamp": "2024-11-01T10:30:00Z",
    "decision": "APPROVED",
    "approved_amount": 1350.00,
    "confidence_score": 0.92,
    "message": "Claim approved. 10% co-pay applied (₹150 deducted from ₹1,500).",
    "trace": [
        {
            "step": "input_validation",
            "status": "PASSED",
            "duration_ms": 5,
            "details": "Member EMP001 valid. Policy active. Amount ₹1,500 within limits."
        },
        {
            "step": "document_verification",
            "status": "PASSED",
            "duration_ms": 1200,
            "details": "2 documents classified: PRESCRIPTION (confidence 0.95), HOSPITAL_BILL (confidence 0.92). All required docs present. Patient names match: 'Rajesh Kumar'."
        },
        {
            "step": "data_extraction",
            "status": "PASSED",
            "duration_ms": 2100,
            "details": "Prescription: Dr. Arun Sharma, KA/45678/2015, Viral Fever. Bill: City Clinic, ₹1,500 total, 3 line items."
        },
        {
            "step": "policy_evaluation",
            "status": "PASSED",
            "duration_ms": 800,
            "details": "No waiting period applicable. No exclusions matched. No pre-auth required. Network discount: N/A (not network hospital). Co-pay: 10% = ₹150. Approved amount: ₹1,350."
        },
        {
            "step": "fraud_detection",
            "status": "PASSED",
            "duration_ms": 3,
            "details": "No fraud signals detected. Same-day claims: 0/2. Monthly claims: within limit."
        },
        {
            "step": "decision_aggregation",
            "status": "COMPLETED",
            "duration_ms": 2,
            "details": "All checks passed. Decision: APPROVED. Confidence: 0.92."
        }
    ]
}
```

---

## 6. LLM Strategy

### 6.1 Model Choice

**Gemini 2.0 Flash** for all LLM calls. Reasons:

- Cheapest production-grade vision model ($0.10/1M input tokens).
- Native JSON mode for structured output.
- Sub-second latency for text-only calls.
- Adequate accuracy for document classification and structured extraction.

### 6.2 Call Budget Per Claim

| Call | Type | Estimated Tokens | Estimated Cost |
|------|------|-----------------|----------------|
| Doc Gatekeeper (per doc, ~2 docs) | Vision | ~2,000 input + 500 output per doc | ₹0.05 |
| Data Extraction (per doc, ~2 docs) | Vision | ~2,000 input + 1,000 output per doc | ₹0.08 |
| Policy Eval - Exclusion Matching | Text | ~500 input + 200 output | ₹0.005 |
| **Total per claim** | | | **~₹0.15** |

### 6.3 Prompt Strategy

All LLM calls use:

1. **System prompt** with role definition and output schema.
2. **Structured output** — Gemini JSON mode with explicit schema. No free-text parsing.
3. **Few-shot examples** embedded in system prompts for document classification and extraction.
4. **Temperature 0** for deterministic, reproducible output.
5. **Timeout handling** — 30-second timeout per call. On timeout, the orchestrator catches the error and continues with degraded confidence.

### 6.4 Prompt Consolidation

To reduce API calls:

- **Document Gatekeeper:** Single call per document that returns classification, quality assessment, AND patient name extraction in one structured response.
- **Data Extraction:** Single call per document that returns all extracted fields in one structured response.
- **Policy Evaluator LLM:** Single call that takes the full extracted data and returns ALL semantic classifications (exclusion matches, condition mappings, procedure coverage) in one response.

This means a typical 2-document claim makes **5 Gemini calls total** (2 gatekeeper + 2 extraction + 1 policy classification).

---

## 7. Observability Design

### 7.1 Audit Trail

Every claim produces a `ClaimTrace` object that is persisted alongside the decision. The trace is:

- **Complete** — every pipeline step is recorded, including skipped/failed steps.
- **Reconstructable** — given only the trace, an ops team member can understand exactly why the claim got its decision.
- **Timestamped** — each step records start time and duration.

### 7.2 What Gets Logged Per Step

| Step | What's Captured |
|------|----------------|
| Input Validation | All checks performed and their results |
| Document Gatekeeper | Per-document: classified type, confidence, quality, patient name found |
| Data Extraction | Per-document: all extracted fields with per-field confidence scores |
| Policy Evaluator | Each rule checked, result, source (DETERMINISTIC vs LLM), and calculation breakdown |
| Fraud Detection | Each threshold checked, current value vs limit |
| Decision Aggregation | Final decision reasoning, confidence calculation breakdown |

### 7.3 Trace Viewer UI

The Streamlit "Review Decisions" page shows:

- Claim summary (member, category, amount, date).
- Decision with approved amount and confidence.
- Expandable trace — click each step to see full details.
- Document previews alongside extracted data.
- Calculation breakdown showing each deduction.

---

## 8. Error Handling and Graceful Degradation

### 8.1 Error Categories

| Category | Example | Handling |
|----------|---------|----------|
| Validation Error | Invalid member ID | Return specific error, stop pipeline |
| Document Error | Missing required doc, unreadable doc | Return specific error, stop pipeline |
| LLM Timeout | Gemini call exceeds 30s | Catch, record in trace, continue with degraded confidence |
| LLM Parse Error | Gemini returns non-JSON | Retry once with stricter prompt; if still fails, treat as timeout |
| Extraction Failure | Cannot extract required field | Set field to null, reduce confidence, continue |
| Component Crash | Unexpected exception in any agent | Catch, record in trace, skip agent, reduce confidence significantly |

### 8.2 Graceful Degradation Protocol (TC011)

When `simulate_component_failure` is `true` in the input, or when any component genuinely fails:

1. The orchestrator wraps each agent call in try/catch.
2. On failure: record a `TraceStep` with `status: FAILED` and the error message.
3. Continue to next agent with whatever data is available.
4. The Decision Aggregator:
   - Deducts 0.30 from confidence per failed component.
   - Adds a note: "Component [X] failed and was skipped. Manual review recommended."
   - Still produces a decision if enough data is available.
   - Never returns HTTP 500.

### 8.3 Simulating Component Failure

For TC011, when `simulate_component_failure: true` is in the input, the orchestrator will deliberately cause the fraud detection agent to raise an exception before running. This is the safest component to fail because:

- It doesn't produce data needed by other agents.
- The claim can still get an accurate approval/rejection without it.
- It demonstrates graceful degradation without corrupting the decision.

---

## 9. Data Models (Summary)

Detailed data models are in the LLD. Here is the summary:

### 9.1 Core Entities

| Entity | Purpose |
|--------|---------|
| `ClaimSubmission` | Input from the member: member_id, category, amount, documents |
| `PolicyConfig` | Loaded from `policy_terms.json` at startup: all rules, members, thresholds |
| `DocumentVerificationResult` | Output from Document Gatekeeper: classifications, quality, issues |
| `ExtractedClaimData` | Output from Data Extractor: structured fields per document |
| `PolicyEvaluationResult` | Output from Policy Evaluator: checks passed/failed, approved amount, deductions |
| `FraudCheckResult` | Output from Fraud Detector: signals, score, manual review flag |
| `ClaimDecision` | Final output: verdict, amount, confidence, full trace |
| `AuditTrace` | List of TraceSteps with per-step details |

### 9.2 Database Schema (SQLite)

Three tables for persistence:

- `claims` — claim submissions with metadata.
- `decisions` — claim decisions with verdict, amount, confidence.
- `traces` — full JSON trace per claim (stored as TEXT).

This is intentionally simple. The architecture doc for Plum will describe the production schema (PostgreSQL/DynamoDB).

---

## 10. Deployment Architecture

### 10.1 Evaluation Deployment

```
┌──────────────────────────────┐
│   Streamlit Community Cloud  │
│   (or Render free tier)      │
│                              │
│   ┌──────────────────────┐   │
│   │   Streamlit App      │   │
│   │   (Python monolith)  │   │
│   │                      │   │
│   │   ├── UI pages       │   │
│   │   ├── Orchestrator   │   │
│   │   ├── All agents     │   │
│   │   └── SQLite DB      │   │
│   └──────────────────────┘   │
│              │                │
│              ▼                │
│   ┌──────────────────────┐   │
│   │ Gemini API (external)│   │
│   └──────────────────────┘   │
└──────────────────────────────┘
```

**Why monolith for evaluation:** Zero deployment complexity. One `streamlit run app/main.py` and the entire system is running. The agents are Python modules within the same process — function calls, not network calls.

### 10.2 Production Deployment (Architecture Doc for Plum)

At 10x scale, the system would decompose into:

- **API Gateway** (AWS API Gateway) — receives claim submissions.
- **Orchestrator** (AWS Step Functions) — sequences agent calls as a state machine.
- **Document Processing** (AWS Lambda + S3) — document upload to S3, triggers Lambda for Gemini calls.
- **Policy Engine** (AWS Lambda) — deterministic evaluation, no LLM.
- **Decision Store** (DynamoDB) — claim decisions and traces.
- **Monitoring** (CloudWatch + X-Ray) — observability.

This decomposition is described in the architecture doc deliverable but NOT implemented for the evaluation.

---

## 11. Key Assumptions

These are assumptions made where the policy document or test cases were ambiguous:

| # | Assumption | Justification |
|---|-----------|---------------|
| A1 | `sub_limit` per category is an annual category cap, not a per-claim cap. | TC010 claims ₹4,500 for CONSULTATION (sub_limit ₹2,000) and is approved for ₹3,240. If sub_limit were per-claim, this would fail. |
| A2 | When per-category YTD amount is not provided, the sub_limit annual cap check is skipped. | Test cases provide `ytd_claims_amount` as a total across all categories, not per-category. |
| A3 | `per_claim_limit` (₹5,000) is a hard rejection gate, not a cap-down. | TC008 claims ₹7,500 and is REJECTED, not PARTIAL with ₹5,000. |
| A4 | The effective per-claim cap is `max(per_claim_limit, category_sub_limit)`. | TC006 (dental, ₹12,000 claimed, ₹8,000 after filtering) passes because `max(5000, 10000) = 10,000 > 8,000`. TC008 (consultation, ₹7,500) fails because `max(5000, 2000) = 5,000 < 7,500`. |
| A5 | Per-claim cap is checked on the post-line-item-filtering amount, not the original claimed amount. | TC006 claimed ₹12,000 but after removing excluded items, approved amount is ₹8,000 which is under the ₹10,000 effective cap. |
| A6 | Network discount is applied BEFORE copay. Copay is calculated on the discounted amount. | Explicitly stated in TC010 expected output. |
| A7 | Fraud signals trigger MANUAL_REVIEW, never automatic rejection. | TC009 expects MANUAL_REVIEW, not REJECTED. |
| A8 | For graceful degradation (TC011), the fraud detector is the component that fails, as it is the safest to skip. | The fraud detector does not produce data consumed by other agents, making it the cleanest failure simulation. |

---

## 12. Test Case Verification

Verified the calculation waterfall against all 12 test cases:

| TC | Category | Claimed | Expected Decision | Expected Amount | Waterfall Result | Match? |
|----|----------|---------|-------------------|-----------------|-----------------|--------|
| TC001 | CONSULTATION | ₹1,500 | STOP (doc error) | — | Doc Gatekeeper: missing HOSPITAL_BILL | ✓ |
| TC002 | PHARMACY | ₹800 | STOP (unreadable) | — | Doc Gatekeeper: PHARMACY_BILL unreadable | ✓ |
| TC003 | CONSULTATION | ₹1,500 | STOP (name mismatch) | — | Doc Gatekeeper: name mismatch | ✓ |
| TC004 | CONSULTATION | ₹1,500 | APPROVED | ₹1,350 | 1500 × 0.90 (10% copay) = 1,350 | ✓ |
| TC005 | CONSULTATION | ₹3,000 | REJECTED | — | Waiting period: diabetes 90d, joined Sep 1, treated Oct 15 (44d < 90d) | ✓ |
| TC006 | DENTAL | ₹12,000 | PARTIAL | ₹8,000 | Root canal ₹8,000 approved, whitening ₹4,000 excluded. 0% copay. | ✓ |
| TC007 | DIAGNOSTIC | ₹15,000 | REJECTED | — | MRI ₹15,000 > ₹10,000 threshold, no pre-auth | ✓ |
| TC008 | CONSULTATION | ₹7,500 | REJECTED | — | ₹7,500 > effective cap max(5000,2000) = ₹5,000 | ✓ |
| TC009 | CONSULTATION | ₹4,800 | MANUAL_REVIEW | — | 4 same-day claims > 2 limit | ✓ |
| TC010 | CONSULTATION | ₹4,500 | APPROVED | ₹3,240 | 4500 × 0.80 (20% network disc) = 3600 × 0.90 (10% copay) = 3,240 | ✓ |
| TC011 | ALT_MEDICINE | ₹4,000 | APPROVED (degraded) | ₹4,000 | 0% copay, not network. Component failure noted, lower confidence. | ✓ |
| TC012 | CONSULTATION | ₹8,000 | REJECTED | — | All items match exclusions (obesity/bariatric) | ✓ |

All 12 test cases pass the calculation waterfall.

---

## 13. Trade-Offs and Design Decisions

### 13.1 Decisions Made

| Decision | Alternative Considered | Why We Chose This |
|----------|----------------------|-------------------|
| Streamlit over React | React would give a better UI | 2-3 day timeline; Streamlit is 5x faster to build |
| Gemini Flash over Claude/GPT-4o | Claude is more accurate for reasoning | Gemini Flash is 10-20x cheaper for vision; accuracy sufficient for document extraction |
| SQLite over PostgreSQL | PostgreSQL is production-grade | Zero deployment cost; sufficient for 12 test cases |
| Monolith over microservices | Microservices scale independently | Single-process deployment is simpler; agents are still cleanly separated in code |
| Deterministic policy engine over full-LLM | LLM could handle all policy logic | Financial calculations must be exact; LLM adds non-determinism and cost for no benefit |
| Fraud detector as failure simulation target | Could fail any component | Fraud detector is the only agent whose failure doesn't corrupt data for downstream agents |

### 13.2 Known Limitations

1. **No real document uploads for test cases** — Test cases provide structured content in JSON, not actual images. The system handles both modes (real upload → Gemini Vision, test case → use provided content), but the eval primarily tests the logic, not the OCR quality.

2. **No per-category YTD tracking** — The test cases don't provide per-category year-to-date amounts, so the annual sub-limit check is skipped. In production, this would be tracked in the database.

3. **Single-user system** — No authentication, no multi-tenancy. This is an evaluation demo.

4. **No document storage** — Uploaded documents are processed in-memory and not persisted. In production, they'd go to S3.

5. **Synchronous processing** — The Streamlit UI blocks while the pipeline runs. At scale, this would be async with a queue.

---

## 14. File Structure

```
health-claims-processor/
├── README.md                          # Setup instructions and project overview
├── requirements.txt                   # Python dependencies
├── .env.example                       # GEMINI_API_KEY placeholder
├── policy_terms.json                  # Policy configuration (provided)
├── test_cases.json                    # 12 test scenarios (provided)
│
├── app/
│   ├── main.py                        # Streamlit entry point + page config
│   ├── pages/
│   │   ├── 1_Submit_Claim.py          # Claim submission UI
│   │   ├── 2_Review_Decisions.py      # Decision review + trace viewer
│   │   └── 3_Run_Eval.py             # Run all 12 test cases
│   │
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   └── pipeline.py                # Main orchestrator — sequences agents
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── input_validator.py         # Agent 1: Input validation
│   │   ├── document_gatekeeper.py     # Agent 2: Doc verification (LLM)
│   │   ├── data_extractor.py          # Agent 3: Data extraction (LLM)
│   │   ├── policy_evaluator.py        # Agent 4: Hybrid policy evaluation
│   │   ├── fraud_detector.py          # Agent 5: Fraud detection
│   │   └── decision_aggregator.py     # Agent 6: Decision aggregation
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── claim.py                   # ClaimSubmission, ClaimCategory
│   │   ├── document.py                # DocumentClassification, ExtractionResult
│   │   ├── policy.py                  # PolicyConfig, CoverageCategory
│   │   ├── decision.py                # ClaimDecision, DecisionVerdict
│   │   └── trace.py                   # AuditTrace, TraceStep
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gemini_client.py           # Gemini API wrapper with retry + timeout
│   │   ├── policy_loader.py           # Load and parse policy_terms.json
│   │   └── database.py                # SQLite operations
│   │
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── waiting_period.py          # Waiting period date calculations
│   │   ├── limits.py                  # Per-claim limit, annual limit checks
│   │   ├── copay.py                   # Copay + network discount calculations
│   │   ├── preauth.py                 # Pre-authorization checks
│   │   └── exclusions.py              # LLM-assisted exclusion matching
│   │
│   └── utils/
│       ├── __init__.py
│       ├── date_utils.py              # Date arithmetic helpers
│       └── text_matching.py           # Fuzzy name matching (Levenshtein)
│
├── tests/
│   ├── conftest.py                    # Shared fixtures
│   ├── test_input_validator.py
│   ├── test_document_gatekeeper.py
│   ├── test_data_extractor.py
│   ├── test_policy_evaluator.py
│   ├── test_fraud_detector.py
│   ├── test_decision_aggregator.py
│   ├── test_rules/
│   │   ├── test_waiting_period.py
│   │   ├── test_limits.py
│   │   ├── test_copay.py
│   │   └── test_preauth.py
│   └── test_pipeline_integration.py   # End-to-end pipeline tests
│
├── eval/
│   ├── run_eval.py                    # Execute all 12 test cases
│   ├── generate_mock_docs.py          # Generate mock medical documents for testing
│   └── eval_report.md                 # Generated evaluation report
│
└── docs/
    ├── architecture.md                # Architecture document (Plum deliverable)
    ├── component_contracts.md         # Component interface contracts (Plum deliverable)
    └── trade_offs.md                  # Trade-off documentation (Plum deliverable)
```

---

## End of HLD

The LLD will cover: detailed data models (Pydantic schemas), API contracts per agent (input/output/error types), database schema DDL, Gemini prompt templates, Streamlit page layouts, and the complete test plan.
