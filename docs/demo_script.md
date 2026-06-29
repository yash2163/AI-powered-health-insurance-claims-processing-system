# Plum Claims Processor — Demo Video Flow & Script

This document provides a detailed flow and script for recording the **8–12 minute demo video** for your Plum AI Engineer assignment submission.

---

## ⏱️ Video Breakdown Table

| Section | Timeline | Focus | Screen to Show |
| :--- | :---: | :--- | :--- |
| **1. Intro & Architecture** | 0:00 - 2:00 | Welcome, high-level project goals, multi-agent orchestrator architecture | Tab 2: "System Architecture" on streamlit landing page |
| **2. API Configuration** | 2:00 - 3:15 | Gemini configuration panel in sidebar, credential validation, fallback explanation | Sidebar panel, click "Validate Key" |
| **3. Early Stop Demo** | 3:15 - 5:15 | Uploading mismatching documents (TC003), gatekeeper stop, token cost saving | Page 1: "Submit Claim" form + red warning output |
| **4. E2E Approval Demo** | 5:15 - 8:00 | Uploading clean files (TC004), green approval, explaining the audit trace waterfall | Page 1: "Submit Claim" form + green approved banner + trace logs |
| **5. Core Decisions** | 8:00 - 10:00 | Proud design decision (Hybrid evaluator) & decision to change (async queues) | Main page tabs or codebase folders |

---

## 🎙️ Transcript & Speech Script

### Section 1: Intro & System Architecture (0:00 - 2:00)

**[Visual: Deployed Streamlit homepage on `🏠 Policy Overview` tab]**

> *"Hello everyone! My name is [Your Name], and today I am excited to demonstrate my submission for the Plum AI Engineer assignment: an automated Health Insurance Claims Processing System."*
>
> *"This application processes outpatient department (OPD) claims by coordinating six independent agents. Before we submit any files, let's look at the active policy overview on our dashboard. We are running against the GHI 2024 policy with a sum insured of ₹100,000 per employee, an annual OPD category limit of ₹20,000, and standard sub-limits and co-pays per category."*

**[Visual: Switch to `🏗️ System Architecture & Guide` tab]**

> *"Under the hood, the system coordinates six distinct components in a sequential pipeline orchestrated by a central runner:"*
>
> 1. *"**Input Validator (Deterministic):** Instantly checks member IDs, policy dates, category coverage, and deadlines."*
> 2. *"**Document Gatekeeper (LLM/Vision):** Actively classifies files, checks readability quality, and ensures patient names match consistently across all documents."*
> 3. *"**Data Extractor (LLM/Vision):** Performs OCR to extract structured line-items, diagnosis, and billing info."*
> 4. *"**Policy Evaluator (Hybrid):** Combines LLM semantic matching for exclusions and waits with pure Python calculations for financial deductions."*
> 5. *"**Fraud Detector (Deterministic):** Analyzes claim patterns like daily/monthly submission frequency thresholds."*
> 6. *"**Decision Aggregator (Deterministic):** Compiles the final verdict (Approved, Partial, Rejected, or Manual Review) and builds an explainable audit trace."*

---

### Section 2: Dynamic Gemini API Configuration (2:00 - 3:15)

**[Visual: Point cursor to the Streamlit Sidebar configuration panel]**

> *"One feature I implemented for easy review is the **Gemini API Configuration Panel** right in the sidebar. When you launch the app, it pre-populates variables from your `.env` configuration file if available."*
>
> *"Reviewers can input their own Google AI Studio API key here, select their preferred model—such as `gemini-2.5-flash` or `gemini-3.5-flash`—and click **Validate Key**. The application sends a lightweight validation check to Google's servers. If successful, it displays `🟢 Status: Validated & Active`."*
>
> *"If the key is invalid, rate-limited, or left empty, the system automatically degrades gracefully into **Offline Fallback Mode**. The pipeline will still process successfully using deterministic keyword rules and mock schemas, but will note the degradation and lower the confidence score to `0.65`."*

---

### Section 3: Early Stop Demo — Document Mismatch (3:15 - 5:15)

**[Visual: Navigate to the `Submit Claim` page in the sidebar]**

> *"Let's test our first scenario: a claim that gets stopped early due to document verification issues. This is **TC003: Patient name mismatch across documents**."*
>
> *"First, I'll search for Member ID `EMP001`. Rajesh Kumar is found in the roster. I'll set the claimed category to `CONSULTATION`, set the amount to `1500`, and set the treatment date to `2024/11/01`."*
>
> *"Now, I'll upload two files from our manual test suite directory:*
> * `prescription_rajesh.pdf` *(which belongs to Rajesh Kumar)*
> * `bill_arjun.pdf` *(which is a hospital bill for Arjun Sharma)*
>
> *"I'll click **Submit and Process Claim**."*

**[Visual: Wait 1-2 seconds, show the red alert card that appears under Document Verification]**

> *"As you can see, the pipeline halted immediately at the Document Verification step. The error message is highly specific: `The documents appear to belong to different patients. The prescription is for 'Rajesh Kumar' but the hospital bill is for 'Arjun Sharma'. All documents must be for the same patient.`"*
>
> *"By halting immediately at the Gatekeeper, the orchestrator aborted the pipeline before calling the Data Extractor or Policy Evaluator LLM. This design choice prevents wasteful token processing and API cost on invalid claims."*

---

### Section 4: Successful E2E Approval & Explainable Trace (5:15 - 8:00)

**[Visual: Clear the uploaded files and refresh the Submit Claim form]**

> *"Now, let's look at a successful happy-path claim: **TC004: Clean Consultation Claim**."*
>
> *"I'll enter Member ID `EMP001` again. Category is `CONSULTATION`, treatment date is `2024/11/01`, and the claimed amount is `1500`."*
>
> *"This time, I'll upload the correct files:*
> * `F007.pdf` *(prescription for Rajesh Kumar)*
> * `F008.pdf` *(hospital bill for Rajesh Kumar)*
>
> *"I'll click **Submit and Process Claim**."*

**[Visual: Wait for pipeline spinner to complete, show the green `✅ Claim Approved` card]**

> *"Success! The claim is approved. The approved amount is **₹1,350.00** instead of the claimed ₹1,500.00. The system notes that a 10% co-pay deduction was applied."*
>
> *"Let's expand the **Explainable Audit Trace** to see the logic waterfall of our agents:"*
>
> * *"**Input Validation:** Passed. The member is active, treatment date is within policy limits, amount is above the ₹500 minimum, and category is covered."*
> * *"**Document Verification:** Passed. It classified both files, verified their quality as GOOD, and confirmed that the patient names are consistent."*
> * *"**Data Extraction:** Passed. It extracted the diagnosis `Viral Fever` and mapped the itemized lines from the bill."*
> * *"**Policy Evaluation:** Passed. It performed a waiting period check (no match), exclusion check (no match), and calculated the copay: 10% co-pay on ₹1,500 = ₹150 deducted. Net approved amount: ₹1,350.00."*
> * *"**Fraud Detection:** Passed. Checks completed successfully: 1 same-day claim, 1 monthly claim. Within limits."*
> * *"**Decision Aggregator:** Compiled the APPROVED decision with a confidence score of `0.95`."*
>
> *"Every single step is transparent, explainable, and logged in our SQLite database for future review."*

---

### Section 5: Technical Decisions & Trade-Offs (8:00 - 10:00)

**[Visual: Switch to Streamlit code editor or main page tab]**

> *"To wrap up, I'll share two core technical design decisions."*
>
> *"**First, a decision I am genuinely proud of: The Hybrid Policy Evaluator architecture.**"*
> * *"When evaluating insurance terms, many developers feed the policy guidelines and raw data into a large prompt and ask the LLM to calculate the final approved amount. This leads to non-deterministic math hallucinations and high token costs."*
> * *"Instead, I designed a Hybrid Evaluator. We use the LLM strictly for **semantic classification** (e.g. mapping clinical diagnosis text to exclusion conditions or waiting periods), but the actual calculations—discounts, co-pays, sub-limit exhaustion, and annual caps—are computed using pure Python. This guarantees 100% calculation accuracy, zero math errors, complete reproducibility, and keeps API costs under ₹0.01 per policy evaluation."*
>
> *"**Second, a decision I would change given more time: Synchronous UI processing.**"*
> * *"Currently, the Streamlit interface blocks synchronously while the pipeline runs. If an LLM call experiences high latency, the user is left waiting."*
> * *"In a production environment, I would refactor this into an **asynchronous event-driven architecture**. When a user submits a claim, the web app would place the claim into a message queue (like AWS SQS or RabbitMQ) and immediately return a 'Processing' status. Background worker pools would pick up the tasks, process the agents, and write results back to the database, allowing the system to scale horizontally to 100k+ claims per day without blocking users."*
>
> *"Thank you for your time, and I look forward to your feedback!"*
