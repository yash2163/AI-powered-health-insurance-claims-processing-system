# Evaluation Report: Health Claims Processor

Generated at: 2026-06-27 11:43:40

## Summary

Total Test Cases: **12**  
Passed: **12**  
Failed: **0**  

### Test Results Grid

| TC ID | Name | Expected Decision | Expected Amount | Actual Decision | Actual Amount | Status |
|---|---|---|---|---|---|---|
| TC001 | Wrong Document Uploaded | STOP (error) | — | STOP (error) | — | ✅ PASSED |
| TC002 | Unreadable Document | STOP (error) | — | STOP (error) | — | ✅ PASSED |
| TC003 | Documents Belong to Different Patients | STOP (error) | — | STOP (error) | — | ✅ PASSED |
| TC004 | Clean Consultation — Full Approval | APPROVED | ₹1,350.00 | APPROVED | ₹1,350.00 | ✅ PASSED |
| TC005 | Waiting Period — Diabetes | REJECTED | — | REJECTED | ₹0.00 | ✅ PASSED |
| TC006 | Dental Partial Approval — Cosmetic Exclusion | PARTIAL | ₹8,000.00 | PARTIAL | ₹8,000.00 | ✅ PASSED |
| TC007 | MRI Without Pre-Authorization | REJECTED | — | REJECTED | ₹0.00 | ✅ PASSED |
| TC008 | Per-Claim Limit Exceeded | REJECTED | — | REJECTED | ₹0.00 | ✅ PASSED |
| TC009 | Fraud Signal — Multiple Same-Day Claims | MANUAL_REVIEW | — | MANUAL_REVIEW | ₹0.00 | ✅ PASSED |
| TC010 | Network Hospital — Discount Applied | APPROVED | ₹3,240.00 | APPROVED | ₹3,240.00 | ✅ PASSED |
| TC011 | Component Failure — Graceful Degradation | APPROVED | — | APPROVED | ₹4,000.00 | ✅ PASSED |
| TC012 | Excluded Treatment | REJECTED | — | REJECTED | ₹0.00 | ✅ PASSED |

---

## Detailed Test Traces

### TC001: Wrong Document Uploaded

**Description:** Member submits two prescriptions for a consultation claim that requires a prescription and a hospital bill.  
**Status:** ✅ PASSED  
**Notes:** Successfully stopped early. Error: Your consultation claim requires the following documents: HOSPITAL_BILL, PRESCRIPTION. We found: PRESCRIPTION. Missing: HOSPITAL_BILL. Please upload your hospital bill and resubmit.  

#### Submission Details
- **Member ID:** `EMP001`
- **Claim Category:** `CONSULTATION`
- **Treatment Date:** `2024-11-01`
- **Claimed Amount:** `₹1,500.00`

#### Execution Trace Logs

```json
[
  {
    "step_name": "input_validation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.178927",
    "duration_ms": 0,
    "details": "Member EMP001 valid. Policy active. Amount \u20b91,500 within limits. Category CONSULTATION covered.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "document_verification",
    "status": "FAILED",
    "started_at": "2026-06-27 06:13:40.178982",
    "duration_ms": 0,
    "details": "Your consultation claim requires the following documents: HOSPITAL_BILL, PRESCRIPTION. We found: PRESCRIPTION. Missing: HOSPITAL_BILL. Please upload your hospital bill and resubmit.",
    "input_summary": null,
    "output_summary": null
  }
]
```

---

### TC002: Unreadable Document

**Description:** Member uploads a valid prescription but a blurry, unreadable photo of their pharmacy bill.  
**Status:** ✅ PASSED  
**Notes:** Successfully stopped early. Error: Your pharmacy bill (blurry_bill.jpg) is not readable. Please re-upload a clearer photo of your pharmacy bill.  

#### Submission Details
- **Member ID:** `EMP004`
- **Claim Category:** `PHARMACY`
- **Treatment Date:** `2024-10-25`
- **Claimed Amount:** `₹800.00`

#### Execution Trace Logs

```json
[
  {
    "step_name": "input_validation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.179283",
    "duration_ms": 0,
    "details": "Member EMP004 valid. Policy active. Amount \u20b9800 within limits. Category PHARMACY covered.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "document_verification",
    "status": "FAILED",
    "started_at": "2026-06-27 06:13:40.179311",
    "duration_ms": 0,
    "details": "Your pharmacy bill (blurry_bill.jpg) is not readable. Please re-upload a clearer photo of your pharmacy bill.",
    "input_summary": null,
    "output_summary": null
  }
]
```

---

### TC003: Documents Belong to Different Patients

**Description:** The prescription is for Rajesh Kumar but the hospital bill is for a different patient, Arjun Mehta.  
**Status:** ✅ PASSED  
**Notes:** Successfully stopped early. Error: The documents appear to belong to different patients. The prescription is for 'Rajesh Kumar' but the hospital bill is for 'Arjun Mehta'. All documents must be for the same patient.  

#### Submission Details
- **Member ID:** `EMP001`
- **Claim Category:** `CONSULTATION`
- **Treatment Date:** `2024-11-01`
- **Claimed Amount:** `₹1,500.00`

#### Execution Trace Logs

```json
[
  {
    "step_name": "input_validation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.179347",
    "duration_ms": 0,
    "details": "Member EMP001 valid. Policy active. Amount \u20b91,500 within limits. Category CONSULTATION covered.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "document_verification",
    "status": "FAILED",
    "started_at": "2026-06-27 06:13:40.180248",
    "duration_ms": 0,
    "details": "The documents appear to belong to different patients. The prescription is for 'Rajesh Kumar' but the hospital bill is for 'Arjun Mehta'. All documents must be for the same patient.",
    "input_summary": null,
    "output_summary": null
  }
]
```

---

### TC004: Clean Consultation — Full Approval

**Description:** Complete, valid consultation claim with correct documents, valid member, covered treatment, within all limits.  
**Status:** ✅ PASSED  
**Notes:** Approved amount matches.; Decision and amount match successfully.  

#### Submission Details
- **Member ID:** `EMP001`
- **Claim Category:** `CONSULTATION`
- **Treatment Date:** `2024-11-01`
- **Claimed Amount:** `₹1,500.00`

#### Execution Trace Logs

```json
[
  {
    "step_name": "input_validation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.180437",
    "duration_ms": 0,
    "details": "Member EMP001 valid. Policy active. Amount \u20b91,500 within limits. Category CONSULTATION covered.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "document_verification",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.180459",
    "duration_ms": 0,
    "details": "2 documents classified. All required documents present. Patient names consistent: 'Rajesh Kumar'.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "data_extraction",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.180561",
    "duration_ms": 0,
    "details": "Extracted data from 2 documents. Diagnosis: Viral Fever. Treatment: N/A. Line items: 3. Total amount: \u20b91,500.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "policy_evaluation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.182208",
    "duration_ms": 1,
    "details": "All policy checks passed. Pre-deduction: \u20b91,500. Deductions: 1. Final approved: \u20b91,350.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "fraud_detection",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.182236",
    "duration_ms": 0,
    "details": "Same-day claims: 1/2. Monthly claims: 1/6. High-value: No. No flags raised.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "decision_aggregation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.182270",
    "duration_ms": 0,
    "details": "Decision: APPROVED. Approved: \u20b91,350. Confidence: 0.95.",
    "input_summary": null,
    "output_summary": null
  }
]
```

---

### TC005: Waiting Period — Diabetes

**Description:** Member joined 2024-09-01. Claims for diabetes treatment on 2024-10-15, which is within the 90-day waiting period for diabetes.  
**Status:** ✅ PASSED  
**Notes:** Decision and amount match successfully.  

#### Submission Details
- **Member ID:** `EMP005`
- **Claim Category:** `CONSULTATION`
- **Treatment Date:** `2024-10-15`
- **Claimed Amount:** `₹3,000.00`

#### Execution Trace Logs

```json
[
  {
    "step_name": "input_validation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.182321",
    "duration_ms": 0,
    "details": "Member EMP005 valid. Policy active. Amount \u20b93,000 within limits. Category CONSULTATION covered.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "document_verification",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.182347",
    "duration_ms": 0,
    "details": "2 documents classified. All required documents present. Patient names consistent: 'Vikram Joshi'.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "data_extraction",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.182389",
    "duration_ms": 0,
    "details": "Extracted data from 2 documents. Diagnosis: Type 2 Diabetes Mellitus. Treatment: N/A. Line items: 1. Total amount: \u20b93,000.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "policy_evaluation",
    "status": "FAILED",
    "started_at": "2026-06-27 06:13:40.182510",
    "duration_ms": 0,
    "details": "Policy check failed. Reasons: Diagnosis maps to 'diabetes' which has a 90-day waiting period. Member joined 2024-09-01. Treatment date 2024-10-15 is before eligibility date 2024-11-30. The member will be eligible for diabetes-related claims from 2024-11-30.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "fraud_detection",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.182523",
    "duration_ms": 0,
    "details": "Same-day claims: 1/2. Monthly claims: 1/6. High-value: No. No flags raised.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "decision_aggregation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.182541",
    "duration_ms": 0,
    "details": "Decision: REJECTED. Approved: \u20b90. Confidence: 0.95.",
    "input_summary": null,
    "output_summary": null
  }
]
```

---

### TC006: Dental Partial Approval — Cosmetic Exclusion

**Description:** Bill includes root canal treatment (covered) and teeth whitening (cosmetic, excluded). System must approve only the covered procedure.  
**Status:** ✅ PASSED  
**Notes:** Approved amount matches.; Decision and amount match successfully.  

#### Submission Details
- **Member ID:** `EMP002`
- **Claim Category:** `DENTAL`
- **Treatment Date:** `2024-10-15`
- **Claimed Amount:** `₹12,000.00`

#### Execution Trace Logs

```json
[
  {
    "step_name": "input_validation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.182578",
    "duration_ms": 0,
    "details": "Member EMP002 valid. Policy active. Amount \u20b912,000 within limits. Category DENTAL covered.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "document_verification",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.182592",
    "duration_ms": 0,
    "details": "1 documents classified. All required documents present. Patient names consistent: 'Priya Singh'.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "data_extraction",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.182621",
    "duration_ms": 0,
    "details": "Extracted data from 1 documents. Diagnosis: N/A. Treatment: N/A. Line items: 2. Total amount: \u20b912,000.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "policy_evaluation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.182989",
    "duration_ms": 0,
    "details": "All policy checks passed. Pre-deduction: \u20b98,000. Deductions: 0. Final approved: \u20b98,000. PARTIAL: 1 items excluded.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "fraud_detection",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183002",
    "duration_ms": 0,
    "details": "Same-day claims: 1/2. Monthly claims: 1/6. High-value: No. No flags raised.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "decision_aggregation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183019",
    "duration_ms": 0,
    "details": "Decision: PARTIAL. Approved: \u20b98,000. Confidence: 0.95.",
    "input_summary": null,
    "output_summary": null
  }
]
```

---

### TC007: MRI Without Pre-Authorization

**Description:** MRI scan costing ₹15,000 submitted without pre-authorization. Policy requires pre-auth for MRI above ₹10,000.  
**Status:** ✅ PASSED  
**Notes:** Decision and amount match successfully.  

#### Submission Details
- **Member ID:** `EMP007`
- **Claim Category:** `DIAGNOSTIC`
- **Treatment Date:** `2024-11-02`
- **Claimed Amount:** `₹15,000.00`

#### Execution Trace Logs

```json
[
  {
    "step_name": "input_validation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183059",
    "duration_ms": 0,
    "details": "Member EMP007 valid. Policy active. Amount \u20b915,000 within limits. Category DIAGNOSTIC covered.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "document_verification",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183080",
    "duration_ms": 0,
    "details": "3 documents classified. All required documents present. Patient names consistent: 'N/A'.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "data_extraction",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183113",
    "duration_ms": 0,
    "details": "Extracted data from 3 documents. Diagnosis: Suspected Lumbar Disc Herniation. Treatment: N/A. Line items: 1. Total amount: \u20b915,000.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "policy_evaluation",
    "status": "FAILED",
    "started_at": "2026-06-27 06:13:40.183264",
    "duration_ms": 0,
    "details": "Policy check failed. Reasons: Pre-authorization is required for this treatment (amount \u20b915,000 exceeds threshold). No pre-authorization was obtained. Please obtain pre-authorization from your insurer before undergoing the treatment and resubmit the claim.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "fraud_detection",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183276",
    "duration_ms": 0,
    "details": "Same-day claims: 1/2. Monthly claims: 1/6. High-value: No. No flags raised.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "decision_aggregation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183290",
    "duration_ms": 0,
    "details": "Decision: REJECTED. Approved: \u20b90. Confidence: 0.95.",
    "input_summary": null,
    "output_summary": null
  }
]
```

---

### TC008: Per-Claim Limit Exceeded

**Description:** Claimed amount of ₹7,500 exceeds the per-claim limit of ₹5,000.  
**Status:** ✅ PASSED  
**Notes:** Decision and amount match successfully.  

#### Submission Details
- **Member ID:** `EMP003`
- **Claim Category:** `CONSULTATION`
- **Treatment Date:** `2024-10-20`
- **Claimed Amount:** `₹7,500.00`

#### Execution Trace Logs

```json
[
  {
    "step_name": "input_validation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183322",
    "duration_ms": 0,
    "details": "Member EMP003 valid. Policy active. Amount \u20b97,500 within limits. Category CONSULTATION covered.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "document_verification",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183338",
    "duration_ms": 0,
    "details": "2 documents classified. All required documents present. Patient names consistent: 'N/A'.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "data_extraction",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183364",
    "duration_ms": 0,
    "details": "Extracted data from 2 documents. Diagnosis: Gastroenteritis. Treatment: N/A. Line items: 2. Total amount: \u20b97,500.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "policy_evaluation",
    "status": "FAILED",
    "started_at": "2026-06-27 06:13:40.183554",
    "duration_ms": 0,
    "details": "Policy check failed. Reasons: Claimed amount \u20b97,500 exceeds the per-claim limit of \u20b95,000. The maximum allowed per claim for consultation is \u20b95,000.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "fraud_detection",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183568",
    "duration_ms": 0,
    "details": "Same-day claims: 1/2. Monthly claims: 1/6. High-value: No. No flags raised.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "decision_aggregation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183582",
    "duration_ms": 0,
    "details": "Decision: REJECTED. Approved: \u20b90. Confidence: 0.95.",
    "input_summary": null,
    "output_summary": null
  }
]
```

---

### TC009: Fraud Signal — Multiple Same-Day Claims

**Description:** Member EMP008 has already submitted 3 claims today before this one arrives. This is the 4th claim from the same member on the same day.  
**Status:** ✅ PASSED  
**Notes:** Decision and amount match successfully.  

#### Submission Details
- **Member ID:** `EMP008`
- **Claim Category:** `CONSULTATION`
- **Treatment Date:** `2024-10-30`
- **Claimed Amount:** `₹4,800.00`

#### Execution Trace Logs

```json
[
  {
    "step_name": "input_validation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183620",
    "duration_ms": 0,
    "details": "Member EMP008 valid. Policy active. Amount \u20b94,800 within limits. Category CONSULTATION covered.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "document_verification",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183635",
    "duration_ms": 0,
    "details": "2 documents classified. All required documents present. Patient names consistent: 'N/A'.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "data_extraction",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183662",
    "duration_ms": 0,
    "details": "Extracted data from 2 documents. Diagnosis: Migraine. Treatment: N/A. Line items: 1. Total amount: \u20b94,800.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "policy_evaluation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183817",
    "duration_ms": 0,
    "details": "All policy checks passed. Pre-deduction: \u20b94,800. Deductions: 1. Final approved: \u20b94,320.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "fraud_detection",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183836",
    "duration_ms": 0,
    "details": "Same-day claims: 4/2. Monthly claims: 4/6. High-value: No. FLAGGED for manual review.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "decision_aggregation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183850",
    "duration_ms": 0,
    "details": "Decision: MANUAL_REVIEW. Approved: \u20b90. Confidence: 0.95.",
    "input_summary": null,
    "output_summary": null
  }
]
```

---

### TC010: Network Hospital — Discount Applied

**Description:** Valid claim at Apollo Hospitals, a network hospital. Network discount must be applied before co-pay.  
**Status:** ✅ PASSED  
**Notes:** Approved amount matches.; Decision and amount match successfully.  

#### Submission Details
- **Member ID:** `EMP010`
- **Claim Category:** `CONSULTATION`
- **Treatment Date:** `2024-11-03`
- **Claimed Amount:** `₹4,500.00`

#### Execution Trace Logs

```json
[
  {
    "step_name": "input_validation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183884",
    "duration_ms": 0,
    "details": "Member EMP010 valid. Policy active. Amount \u20b94,500 within limits. Category CONSULTATION covered.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "document_verification",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183907",
    "duration_ms": 0,
    "details": "2 documents classified. All required documents present. Patient names consistent: 'Deepak Shah'.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "data_extraction",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.183943",
    "duration_ms": 0,
    "details": "Extracted data from 2 documents. Diagnosis: Acute Bronchitis. Treatment: N/A. Line items: 2. Total amount: \u20b94,500.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "policy_evaluation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.184146",
    "duration_ms": 0,
    "details": "All policy checks passed. Pre-deduction: \u20b94,500. Deductions: 2. Final approved: \u20b93,240.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "fraud_detection",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.184158",
    "duration_ms": 0,
    "details": "Same-day claims: 1/2. Monthly claims: 1/6. High-value: No. No flags raised.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "decision_aggregation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.184177",
    "duration_ms": 0,
    "details": "Decision: APPROVED. Approved: \u20b93,240. Confidence: 0.95.",
    "input_summary": null,
    "output_summary": null
  }
]
```

---

### TC011: Component Failure — Graceful Degradation

**Description:** One component of your system fails mid-processing (simulate with the flag below). The overall pipeline must continue, produce a decision, and make the failure visible in the output with an appropriately reduced confidence score.  
**Status:** ✅ PASSED  
**Notes:** Decision and amount match successfully.  

#### Submission Details
- **Member ID:** `EMP006`
- **Claim Category:** `ALTERNATIVE_MEDICINE`
- **Treatment Date:** `2024-10-28`
- **Claimed Amount:** `₹4,000.00`

#### Execution Trace Logs

```json
[
  {
    "step_name": "input_validation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.184209",
    "duration_ms": 0,
    "details": "Member EMP006 valid. Policy active. Amount \u20b94,000 within limits. Category ALTERNATIVE_MEDICINE covered.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "document_verification",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.184225",
    "duration_ms": 0,
    "details": "2 documents classified. All required documents present. Patient names consistent: 'N/A'.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "data_extraction",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.184252",
    "duration_ms": 0,
    "details": "Extracted data from 2 documents. Diagnosis: Chronic Joint Pain. Treatment: Panchakarma Therapy. Line items: 2. Total amount: \u20b94,000.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "policy_evaluation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.184460",
    "duration_ms": 0,
    "details": "All policy checks passed. Pre-deduction: \u20b94,000. Deductions: 0. Final approved: \u20b94,000.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "fraud_detection",
    "status": "FAILED",
    "started_at": "2026-06-27 06:13:40.184464",
    "duration_ms": 0,
    "details": "Fraud detection failed: Simulated component failure: Fraud detection service unavailable. Skipped \u2014 manual review recommended.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "decision_aggregation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.184478",
    "duration_ms": 0,
    "details": "Decision: APPROVED. Approved: \u20b94,000. Confidence: 0.65.",
    "input_summary": null,
    "output_summary": null
  }
]
```

---

### TC012: Excluded Treatment

**Description:** Member claims for bariatric consultation and a diet program. Obesity treatment is explicitly excluded under the policy.  
**Status:** ✅ PASSED  
**Notes:** Decision and amount match successfully.  

#### Submission Details
- **Member ID:** `EMP009`
- **Claim Category:** `CONSULTATION`
- **Treatment Date:** `2024-10-18`
- **Claimed Amount:** `₹8,000.00`

#### Execution Trace Logs

```json
[
  {
    "step_name": "input_validation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.184510",
    "duration_ms": 0,
    "details": "Member EMP009 valid. Policy active. Amount \u20b98,000 within limits. Category CONSULTATION covered.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "document_verification",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.184526",
    "duration_ms": 0,
    "details": "2 documents classified. All required documents present. Patient names consistent: 'N/A'.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "data_extraction",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.184553",
    "duration_ms": 0,
    "details": "Extracted data from 2 documents. Diagnosis: Morbid Obesity \u2014 BMI 37. Treatment: Bariatric Consultation and Customised Diet Plan. Line items: 2. Total amount: \u20b98,000.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "policy_evaluation",
    "status": "FAILED",
    "started_at": "2026-06-27 06:13:40.184973",
    "duration_ms": 0,
    "details": "Policy check failed. Reasons: Diagnosis maps to 'obesity_treatment' which has a 365-day waiting period. Member joined 2024-04-01. Treatment date 2024-10-18 is before eligibility date 2025-04-01. The member will be eligible for obesity_treatment-related claims from 2025-04-01.; Treatment is excluded under policy. Matched exclusions: Obesity and weight loss programs, Bariatric surgery. Diagnosis 'Morbid Obesity \u2014 BMI 37' and all billed items fall under excluded conditions.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "fraud_detection",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.184985",
    "duration_ms": 0,
    "details": "Same-day claims: 1/2. Monthly claims: 1/6. High-value: No. No flags raised.",
    "input_summary": null,
    "output_summary": null
  },
  {
    "step_name": "decision_aggregation",
    "status": "PASSED",
    "started_at": "2026-06-27 06:13:40.185000",
    "duration_ms": 0,
    "details": "Decision: REJECTED. Approved: \u20b90. Confidence: 0.95.",
    "input_summary": null,
    "output_summary": null
  }
]
```

---

