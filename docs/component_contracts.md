# Component Contracts: health-claims-processor

This document defines the strict data schemas, interfaces, and expected error behaviors for each component of the multi-agent claims engine.

---

## 1. Input Validator

* **Method:** `InputValidator.process(claim: ClaimSubmission, policy: PolicyConfig) -> Tuple[bool, List[str], TraceStep]`
* **Inputs:**
  * `claim`: Pydantic object containing claim metadata (dates, member ID, claimed amount).
  * `policy`: Policy configuration containing submission rules and active members.
* **Outputs:**
  * `passed` (bool): `True` if metadata validation succeeds.
  * `errors` (List[str]): List of validation error details (e.g. invalid date format, member not found).
  * `trace` (TraceStep): Log tracing validation details.
* **Errors:**
  * Invalid/missing fields in Pydantic schema will raise a validation exception at constructor time.

---

## 2. Document Gatekeeper

* **Method:** `DocumentGatekeeper.process(claim: ClaimSubmission, policy: PolicyConfig) -> Tuple[DocumentGatekeeperResult, TraceStep]`
* **Inputs:**
  * `claim`: Claim submission containing uploaded document bytes.
  * `policy`: Policy containing member rosters to verify patient names.
* **Outputs:**
  * `DocumentGatekeeperResult`:
    * `status` (str): `"PASSED"` or `"FAILED"`.
    * `classifications` (List[DocumentClassification]): Contains file ID, type (prescription, bill, etc.), patient name, quality, and issues list.
    * `error_message` (str | None): Populated with explanation if verification failed.
    * `issues` (List[GatekeeperIssue]): Individual issues found.
* **Errors:**
  * If a file upload is corrupted, the vision API returns `"UNREADABLE"` and the gatekeeper gracefully rejects the document, returning `status="FAILED"`.

---

## 3. Data Extractor

* **Method:** `DataExtractor.process(claim: ClaimSubmission, classifications: List[DocumentClassification]) -> Tuple[ExtractedClaimData, TraceStep]`
* **Inputs:**
  * `claim`: Submission containing files and fallback metadata.
  * `classifications`: Enriched metadata from the Gatekeeper.
* **Outputs:**
  * `ExtractedClaimData`:
    * `primary_diagnosis` (str | None)
    * `primary_treatment` (str | None)
    * `line_items` (List[LineItem]): List of `{description, amount}`.
    * `total_extracted_amount` (float)
    * `hospital_name` (str | None)
* **Errors:**
  * Vision API timeouts or parse exceptions are handled by returning a degraded status. The extractor falls back to populating fields using metadata provided in the claim submission (e.g., claimed_amount).

---

## 4. Policy Evaluator

* **Method:** `PolicyEvaluator.process(claim: ClaimSubmission, extracted: ExtractedClaimData, policy: PolicyConfig) -> Tuple[PolicyEvaluationResult, TraceStep]`
* **Inputs:**
  * `claim`: Original submission.
  * `extracted`: Data parsed by the Extractor.
  * `policy`: Policy rules (copays, waiting periods, network hospital listings).
* **Outputs:**
  * `PolicyEvaluationResult`:
    * `all_checks_passed` (bool): If False, the claim is rejected at a policy level.
    * `rejection_reasons` (List[RejectionReason]): e.g., `WAITING_PERIOD`, `EXCLUDED_CONDITION`.
    * `rejection_details` (List[str]): Descriptive reasons.
    * `final_approved_amount` (float): The final payable amount.
    * `deductions` (List[Deduction]): Copays, network discounts, YTD cap adjustments.
* **Errors:**
  * Category missing in config returns a `CLAIM_CATEGORY_EXCLUDED` rejection.

---

## 5. Fraud Detector

* **Method:** `FraudDetector.process(claim: ClaimSubmission, policy: PolicyConfig) -> Tuple[FraudCheckResult, TraceStep]`
* **Inputs:**
  * `claim`: Submission containing current claim details and historical claims array.
  * `policy`: Policy config outlining thresholds.
* **Outputs:**
  * `FraudCheckResult`:
    * `requires_manual_review` (bool): `True` if any threshold was crossed.
    * `signals` (List[FraudSignal]): Detail list of triggered signals (value, threshold, type).
    * `details` (str)
* **Errors:**
  * Empty historical claims arrays are handled gracefully by defaulting count metrics to `1` (representing only the current claim).

---

## 6. Decision Aggregator

* **Method:** `DecisionAggregator.process(...) -> ClaimDecision`
* **Inputs:**
  * `claim`: Submission.
  * `policy_result`: Evaluator output.
  * `fraud_result`: Detector output.
  * `all_trace_steps`: List of previous trace logs.
  * `component_failures`: List of component IDs that failed.
* **Outputs:**
  * `ClaimDecision`:
    * `decision` (str): `"APPROVED"`, `"PARTIAL"`, `"REJECTED"`, or `"MANUAL_REVIEW"`.
    * `approved_amount` (float)
    * `rejection_reasons` (List[str])
    * `confidence_score` (float)
    * `message` (str)
    * `trace` (AuditTrace)
* **Errors:**
  * Generates consistent results regardless of individual agent internal failures (graceful degradation decreases confidence score).
