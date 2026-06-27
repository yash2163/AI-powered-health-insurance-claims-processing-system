# System Architecture Document: health-claims-processor

This document details the architecture, design patterns, decisions, and scaling considerations for the automated Health Insurance Claims Processing System.

---

## 1. System Design and Overview

The system is built as a **Multi-Agent Pipeline**, coordinated by a central orchestrator. Each agent handles a single responsibility, providing a clean separation of concerns, independent testability, and isolated failure domains.

### Architecture Topology Diagram
```
              [Member Claim Submission via Streamlit]
                                │
                                ▼
                       [Claims Orchestrator]
                                │
   ┌───────────────────┬────────┴───────────┬───────────────────┐
   │ (Step 1)          │ (Step 2)           │ (Step 3)          │ (Step 4-6)
   ▼                   ▼                    ▼                   ▼
[Input Validator] ──► [Document Gatekeeper] ──► [Data Extractor] ──► [Policy Evaluator]
(Deterministic)       (LLM/Vision Agent)    (LLM/Vision Agent)  │   (Hybrid Engine)
                                                                │
                                                                ▼
                                                          [Fraud Detector]
                                                          (Deterministic)
                                                                │
                                                                ▼
                                                       [Decision Aggregator]
                                                       (Deterministic)
                                                                │
                                                                ▼
                                                       [Decision Database]
```

---

## 2. Core Components and Agents

1. **Input Validator:** A deterministic validation agent checking claim metadata against policy active dates, member roster existence, minimum amounts, and submission deadlines.
2. **Document Gatekeeper:** A hybrid vision agent that classifies documents (using Gemini Vision in Real Mode or pre-declared metadata in Test Mode), evaluates document legibility, checks for completeness, and matches patient names across files.
3. **Data Extractor:** A hybrid vision agent parsing patient names, diagnoses, treatments, and itemised receipt line items from prescriptions, pharmacy bills, and clinic receipts.
4. **Policy Evaluator:** A hybrid evaluation engine mapping diagnoses semantically (using Gemini Text-only or keyword matching) to specific waiting periods or exclusions, and applying limits, network discounts, and co-pays.
5. **Fraud Detector:** A deterministic history parser identifying anomalous claiming frequencies and high-value claim thresholds.
6. **Decision Aggregator:** An explainability component merging intermediate results, calculating final confidence metrics, and compiling the step-by-step audit trace.

---

## 3. Design Decisions & Trade-Offs

### 1. Hybrid Policy Engine
* **Decision:** We opted for a hybrid policy engine where semantic mappings (diagnosis to excluded condition) are handled by LLM classification, but all financial and mathematical computations are deterministic code.
* **Why:** Financial metrics require 100% precision. Entrusting math calculations to an LLM introduces non-determinism, hallucinations, and unnecessary token costs.
* **Trade-off:** Requires mapping intermediate LLM classifications to deterministic code structures, but guarantees absolute calculations consistency.

### 2. Dual-Mode Verification (Test Mode vs Real Mode)
* **Decision:** Built a dual-mode path. In Test Mode (when test-cases provide pre-extracted metadata), the agents skip Gemini API calls entirely.
* **Why:** Enables running the 12 evaluation test cases instantly, deterministically, and at zero token cost.
* **Trade-off:** In-memory metadata is used during evaluations, meaning the vision parsing accuracy is tested separately.

---

## 4. Limitations and 10x Load Scaling Path

### Current Architecture Limitations
* **Monolithic Streamlit Process:** The Streamlit container executes the pipeline synchronously in the request-response thread. Long vision calls block the UI thread.
* **Single SQLite Persistence:** SQLite locks tables on writes, which would result in concurrency bottlenecks under high load.
* **No Image Storage:** Uploaded files are processed in-memory.

### 10x Load Production Architecture
To scale the engine to process 750,000+ claims annually, the system will decompose into a distributed, event-driven architecture:

```
[API Gateway] ──► [SQS Ingest Queue] ──► [Claims Processor Lambda] ──► [Step Functions Orchestration]
                                                                                │
  ┌───────────────────────┬───────────────────────────┬─────────────────────────┤
  ▼                       ▼                           ▼                         ▼
[Lambda: Validator]     [SNS: Doc Upload S3]        [SQS: Extractor Worker]   [Lambda: Evaluator]
                        [Rekognition/Vision API]    [GPU/LLM Batch Clusters]
```

1. **Orchestrator to Step Functions:** Replace the Python coordinator with **AWS Step Functions**. Each agent runs as a containerized microservice on **AWS Lambda** or **ECS Fargate**.
2. **Asynchronous Processing:** Streamlit submits claims to an API Gateway, which puts the payload into an **Amazon SQS** queue, returning an immediate acknowledgment. The UI polls or opens a WebSocket connection for updates.
3. **Vision Processing Scale-Out:** Raw document uploads go directly to an **Amazon S3** bucket. Document classification and extraction are offloaded to dedicated GPU worker pools or serverless batch API queues.
4. **Relational Scale:** SQLite is replaced by **Amazon Aurora PostgreSQL** with read-replicas for high concurrent claim history queries.
