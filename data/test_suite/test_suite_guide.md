# Plum Claims Processor — UI Manual Testing Guide

This directory contains the mock medical document PDF files generated for the evaluation suite. You can use this guide to manually test any of the 12 default test scenarios directly through the Streamlit web application.

---

## 📋 How to Test

1. Start your local Streamlit server:
   ```bash
   streamlit run app/main.py
   ```
2. Navigate to the **Submit Claim** page in the sidebar.
3. Fill out the fields as specified in the test case below.
4. Upload the corresponding PDF files from `data/test_suite/` in the file uploader.
5. Expand **🛠️ Developer Options (Simulation)** at the bottom of the form to configure any historical claim simulation required (e.g. prior same-day claims or YTD claims) as detailed in the test case.
6. Click **Submit and Process Claim** and compare the verdict and approved amount with the expected outcome.

---

## 🔬 Test Cases

### TC001: Wrong Document Uploaded
* **Description:** Member submits two prescriptions for a consultation claim (requires a prescription and a hospital bill).
* **Inputs to Fill:**
  * **Search Member by ID:** `EMP001` (Rajesh Kumar)
  * **Claim Category:** `CONSULTATION`
  * **Claimed Amount:** `1500`
  * **Treatment Date:** `2024/11/01`
  * **Obtained Pre-Authorization:** Unchecked
* **Files to Upload:**
  * `dr_sharma_prescription.pdf`
  * `another_prescription.pdf`
* **Expected Verdict:** **STOP (Document Error)**
* **Expected Message:** Identifies that only prescriptions were uploaded and that a hospital bill is missing.

---

### TC002: Unreadable Document
* **Description:** Member submits a prescription, but the hospital bill uploaded is unreadable/blurry.
* **Inputs to Fill:**
  * **Search Member by ID:** `EMP004` (Sneha Reddy)
  * **Claim Category:** `CONSULTATION`
  * **Claimed Amount:** `800`
  * **Treatment Date:** `2024/10/25`
  * **Obtained Pre-Authorization:** Unchecked
* **Files to Upload:**
  * `prescription.pdf`
  * `blurry_bill.pdf`
* **Expected Verdict:** **STOP (Document Error)**
* **Expected Message:** Identifies that the bill file is unreadable and asks the user to re-upload.

---

### TC003: Documents Belong to Different Patients
* **Description:** Member submits a prescription for "Rajesh Kumar" but the bill is under "Arjun Sharma".
* **Inputs to Fill:**
  * **Search Member by ID:** `EMP001` (Rajesh Kumar)
  * **Claim Category:** `CONSULTATION`
  * **Claimed Amount:** `1500`
  * **Treatment Date:** `2024/11/01`
  * **Obtained Pre-Authorization:** Unchecked
* **Files to Upload:**
  * `prescription_rajesh.pdf`
  * `bill_arjun.pdf`
* **Expected Verdict:** **STOP (Document Error)**
* **Expected Message:** Flags a patient name mismatch (prescription belongs to Rajesh Kumar but the hospital bill belongs to Arjun Sharma).

---

### TC004: Clean Consultation — Full Approval
* **Description:** Standard clean claim containing correct files, matching patient names, and covered procedures.
* **Inputs to Fill:**
  * **Search Member by ID:** `EMP001` (Rajesh Kumar)
  * **Claim Category:** `CONSULTATION`
  * **Claimed Amount:** `1500`
  * **Treatment Date:** `2024/11/01`
  * **Obtained Pre-Authorization:** Unchecked
* **Files to Upload:**
  * `F007.pdf`
  * `F008.pdf`
* **Expected Verdict:** **APPROVED**
* **Expected Amount:** **₹1,350.00**
* **Deduction Reason:** 10.0% co-pay applied on ₹1,500 = ₹150 deducted.

---

### TC005: Waiting Period — Diabetes
* **Description:** Claim for diabetes consultation within the member's initial 90-day waiting period.
* **Inputs to Fill:**
  * **Search Member by ID:** `EMP005` (Karan Johar - Joined `2024-09-15`)
  * **Claim Category:** `CONSULTATION`
  * **Claimed Amount:** `3000`
  * **Treatment Date:** `2024/10/15`
  * **Obtained Pre-Authorization:** Unchecked
* **Files to Upload:**
  * `F009.pdf`
  * `F010.pdf`
* **Expected Verdict:** **REJECTED**
* **Rejection Reason:** Exceeds waiting period check. Expected eligibility date for Diabetes (90 days from joining) is `2024-12-14`.

---

### TC006: Dental Partial Approval — Cosmetic Exclusion
* **Description:** Dental claim containing both cleaning (covered) and teeth whitening (excluded as cosmetic).
* **Inputs to Fill:**
  * **Search Member by ID:** `EMP002` (Priya Singh)
  * **Claim Category:** `DENTAL`
  * **Claimed Amount:** `12000`
  * **Treatment Date:** `2024/10/15`
  * **Obtained Pre-Authorization:** Unchecked
* **Files to Upload:**
  * `F011.pdf`
* **Expected Verdict:** **PARTIAL APPROVAL**
* **Expected Amount:** **₹8,000.00**
* **Deduction Reason:** Whitening (₹4,000) excluded as cosmetic. Approved Root Canal (₹8,000) has no deductions.

---

### TC007: MRI Without Pre-Authorization
* **Description:** Diagnostic claim containing a high-value MRI test (requires pre-authorization).
* **Inputs to Fill:**
  * **Search Member by ID:** `EMP007` (Vikram Joshi)
  * **Claim Category:** `DIAGNOSTIC`
  * **Claimed Amount:** `15000`
  * **Treatment Date:** `2024/11/02`
  * **Obtained Pre-Authorization:** Unchecked
* **Files to Upload:**
  * `F012.pdf`
  * `F013.pdf`
  * `F014.pdf`
* **Expected Verdict:** **REJECTED**
* **Rejection Reason:** Pre-authorization is required for MRI scans.

---

### TC008: Per-Claim Limit / YTD Exceeded
* **Description:** Claimed amount exceeds the per-claim cap on Vision category.
* **Inputs to Fill:**
  * **Search Member by ID:** `EMP003` (Amit Verma)
  * **Claim Category:** `VISION`
  * **Claimed Amount:** `7500`
  * **Treatment Date:** `2024/10/20`
  * **Obtained Pre-Authorization:** Unchecked
  * **🛠️ Developer Options (Simulation):** Set **Simulate YTD Claims Amount** to `10000.00`
* **Files to Upload:**
  * `F015.pdf`
  * `F016.pdf`
* **Expected Verdict:** **REJECTED**
* **Rejection Reason:** Claimed amount exceeds the Vision per-claim limit (or caps to 0 based on YTD limit exhaustion).

---

### TC009: Fraud Signal — Multiple Same-Day Claims
* **Description:** Member submits a 4th claim on the same day (violates same-day threshold of 2).
* **Inputs to Fill:**
  * **Search Member by ID:** `EMP008` (Maya Patel)
  * **Claim Category:** `CONSULTATION`
  * **Claimed Amount:** `4800`
  * **Treatment Date:** `2024/10/30`
  * **Obtained Pre-Authorization:** Unchecked
  * **🛠️ Developer Options (Simulation):** Set **Simulate Prior Claims Today** to `3`
* **Files to Upload:**
  * `F017.pdf`
  * `F018.pdf`
* **Expected Verdict:** **MANUAL REVIEW** (due to potential fraud signals)
* **Expected Signal:** Flags a same-day submission warning (claims limit exceeded: 4/2).

---

### TC010: Network Hospital — Discount Applied
* **Description:** Claim from a network hospital where a 15% discount is applied before co-pay.
* **Inputs to Fill:**
  * **Search Member by ID:** `EMP010` (Arjun Sharma)
  * **Claim Category:** `CONSULTATION`
  * **Claimed Amount:** `4500`
  * **Treatment Date:** `2024/11/03`
  * **Hospital/Clinic Name:** `Apollo Hospital`
  * **Obtained Pre-Authorization:** Unchecked
* **Files to Upload:**
  * `F019.pdf`
  * `F020.pdf`
* **Expected Verdict:** **APPROVED**
* **Expected Amount:** **₹3,442.50** (or 15% discount then 10% co-pay applied on ₹4,500: ₹4,500 - 15% = ₹3,825. Then 10% co-pay = ₹3,442.50)

---

### TC011: Component Failure — Graceful Degradation
* **Description:** Pipeline experiences an exception in the Fraud detection agent, degrading score but processing successfully.
* **Inputs to Fill:**
  * **Search Member by ID:** `EMP006` (Rohan Mehta)
  * **Claim Category:** `CONSULTATION`
  * **Claimed Amount:** `4000`
  * **Treatment Date:** `2024/10/28`
  * **Obtained Pre-Authorization:** Unchecked
  * **🛠️ Developer Options (Simulation):** Check **Simulate Component Failure**
* **Files to Upload:**
  * `F021.pdf`
  * `F022.pdf`
* **Expected Verdict:** **APPROVED**
* **Expected Amount:** **₹3,600.00** (10% co-pay deducted)
* **Expected Confidence:** Degraded to `0.65` (due to simulated fraud service failure).

---

### TC012: Excluded Treatment
* **Description:** Consultation claim for cosmetic surgery (fully excluded treatment condition).
* **Inputs to Fill:**
  * **Search Member by ID:** `EMP009` (Alok Gupta)
  * **Claim Category:** `CONSULTATION`
  * **Claimed Amount:** `8000`
  * **Treatment Date:** `2024/10/18`
  * **Obtained Pre-Authorization:** Unchecked
* **Files to Upload:**
  * `F023.pdf`
  * `F024.pdf`
* **Expected Verdict:** **REJECTED**
* **Rejection Reason:** Excluded condition: Cosmetic / Bariatric surgery is fully excluded.
