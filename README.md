# Health Insurance Claims Processing System

An automated multi-agent pipeline that processes OPD health insurance claims — from document verification through policy evaluation to a final, fully explainable decision.

Built for the Plum AI Engineer assignment.

**[Live Demo →](DEPLOYED_URL_HERE)** · **[Eval Report →](eval/eval_report.md)** · **[Architecture Doc →](docs/HLD.md)**

---

## 🏗️ How It Works

A claim enters the pipeline and passes through six agents in sequence. Each agent has a single responsibility, produces a trace step for the audit log, and can fail independently without crashing the system.

```
Claim Submitted
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                             │
│  Sequences agents, catches failures, accumulates audit trace    │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │   INPUT       │───▶│  DOCUMENT     │───▶│  DATA            │  │
│  │   VALIDATOR   │    │  GATEKEEPER   │    │  EXTRACTOR       │  │
│  │  Deterministic│    │  Gemini Vision│    │  Gemini Vision   │  │
│  └──────────────┘    └──────┬───────┘    └────────┬─────────┘  │
│                             │ STOP on              │            │
│                             │ doc issues            ▼            │
│                             │             ┌──────────────────┐  │
│                             │             │  POLICY           │  │
│                             │             │  EVALUATOR        │  │
│                             │             │  Hybrid (LLM +    │  │
│                             │             │  deterministic)   │  │
│                             │             └────────┬─────────┘  │
│                             │                      │            │
│                             │                      ▼            │
│  ┌──────────────┐           │             ┌──────────────────┐  │
│  │  DECISION     │◀──────────┴────────────│  FRAUD            │  │
│  │  AGGREGATOR   │                        │  DETECTOR         │  │
│  │  Deterministic│                        │  Deterministic    │  │
│  └──────┬───────┘                        └──────────────────┘  │
└─────────┼───────────────────────────────────────────────────────┘
          ▼
  APPROVED | PARTIAL | REJECTED | MANUAL_REVIEW
  + full audit trace
```

The **Document Gatekeeper** acts as a strict check: if documents are missing, blurry/unreadable, or belong to different patients, the pipeline halts immediately with a clear, actionable error message.

---

## 🚀 Features

1. **Multi-Agent Pipeline:**
   * **Input Validator:** Audits claim metadata (dates, rosters, category coverage, and deadlines) deterministically.
   * **Document Gatekeeper:** Performs visual document classification, quality assurance, and patient name consistency checks using fuzzy matching.
   * **Data Extractor:** Parses unstructured prescriptions, bills, and reports into clean, structured JSON schemas.
   * **Policy Evaluator:** Performs semantic matching of exclusions and waiting periods, and runs deterministic calculations for network discounts, co-pays, and sub-limits.
   * **Fraud Detector:** Flags anomalous patterns (e.g. multiple claims submitted on the same day or month).
   * **Decision Aggregator:** Calculates final confidence scores and compiles the explainable audit trace.
2. **Interactive Streamlit UI:**
   * **Submit Claim Form:** Intuitive submission interface supporting multi-document file uploads and live processing.
   * **Review Decisions Database:** Drill down into decision records, filter by categories or verdicts, and inspect detailed visual audit traces.
   * **Evaluation Suite Runner:** Runs custom or predefined test scenarios and generates verification metrics reports in real-time.
3. **🔑 Interactive Gemini API Config Panel:** A dedicated sidebar configuration widget that allows users to input their own Google AI Studio API key and model at runtime, validate connectivity instantly with a confirmation status indicator, or reset/change credentials on the fly.
4. **🛠️ Developer Simulation Panel:** Integrated "Developer Options" in the claim form to simulate historical context (e.g. prior same-day claims or YTD claims) directly from the UI, making it simple to test limit exhaustion and frequency fraud gates.
5. **🔄 Auto-Generating Assets:** Streamlit dynamically auto-generates mock PDF test assets inside the server container on start-up, enabling seamless cloud deployments.
6. **Graceful Degradation:** Employs fallback keyword classifiers and handles internal agent service exceptions gracefully, keeping the pipeline online at a lower confidence score (e.g., `0.65`).

---

## 🧪 Evaluation Results

All 12 evaluation test cases pass successfully. Each row links a test scenario to the pipeline's actual output.

| Case ID | Test Case | Target Agent | Expected Output | Result |
|---|---|---|---|---|
| **TC001** | Wrong document uploaded | Document Gatekeeper | STOP — missing required bill | ✅ |
| **TC002** | Unreadable document | Document Gatekeeper | STOP — re-upload needed | ✅ |
| **TC003** | Patient name mismatch across docs | Document Gatekeeper | STOP — patient names don't match | ✅ |
| **TC004** | Clean consultation claim | Full Pipeline | APPROVED (10% co-pay deduction) | ✅ |
| **TC005** | Diabetes waiting period | Policy Evaluator | REJECTED (within 90-day waiting period) | ✅ |
| **TC006** | Dental: root canal + teeth whitening | Policy Evaluator | PARTIAL (Teeth whitening excluded) | ✅ |
| **TC007** | MRI without pre-authorization | Policy Evaluator | REJECTED (High-value MRI requires pre-auth) | ✅ |
| **TC008** | Claim exceeds per-claim limit | Policy Evaluator | REJECTED (Exceeds category sub-limit) | ✅ |
| **TC009** | 4 claims on same day | Fraud Detector | MANUAL_REVIEW (Exceeds daily limit) | ✅ |
| **TC010** | Network hospital discount + copay | Policy Evaluator | APPROVED (Apollo 15% discount applied first) | ✅ |
| **TC011** | Component failure mid-pipeline | Orchestrator | APPROVED (Graceful degradation, confidence 0.65) | ✅ |
| **TC012** | Bariatric / obesity exclusion | Policy Evaluator | REJECTED (Cosmetic/obesity surgery excluded) | ✅ |

Full trace outputs for every test case are documented in the [eval report](eval/eval_report.md).

---

## 🔑 Key Design Decisions

**Hybrid policy evaluator, not full-LLM.** Financial calculations (copay, discounts, limits) are written as deterministic python rules — exact, reproducible, and zero-cost. The LLM is used only for semantic classification: mapping `"Type 2 Diabetes Mellitus"` to the `diabetes` waiting period, or recognizing that `"Bariatric Consultation"` falls under the obesity exclusion. This limits LLM calls to one text-only request per claim for policy classification, alongside the vision calls for document processing.

**Calculation waterfall order matters.** TC010 requires network discount (15%) before copay (10%), not after. The engine applies: line-item filtering → per-claim cap check → network discount → copay → annual limit check. The per-claim cap uses `max(per_claim_limit, category_sub_limit)` and is checked on the post-filtering amount — this is the only interpretation that passes both TC006 (dental ₹12K → ₹8K partial) and TC008 (consultation ₹7.5K → rejected).

**Fraud detector is the graceful degradation target.** When simulating component failure (TC011), the fraud detector is the safest agent to skip — it produces no data consumed by downstream agents, so its failure doesn't corrupt the decision. The orchestrator catches the exception, records it in the trace, drops confidence to 0.65, and continues.

**Dual-mode architecture.** Every agent handles both test-mode (pre-provided metadata from the evaluation suite) and real-mode (actual uploads processed through Gemini Vision). Predefined test cases run deterministically at zero API cost. Live document uploads trigger the full vision pipeline.

---

## 🛠️ Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Language | Python 3.10+ | AI/ML ecosystem, Gemini SDK, Pydantic |
| Frontend | Streamlit | Fastest path to a working UI with file uploads |
| LLM | Gemini 2.5 Flash | Cost-effective, high-accuracy vision and text reasoning model |
| Policy engine | Deterministic Python | Financial calculations must be exact, fast, and reproducible |
| Database | SQLite | Zero-cost, zero-infrastructure serverless relational database |
| Matching | python-Levenshtein | Fuzzy patient name matching across documents |

---

## 📁 Project Structure (Submission Branch)

```
├── app/
│   ├── main.py                          # Streamlit landing page & architectural guide
│   ├── config.py                        # Constants & environment variables
│   ├── pages/
│   │   ├── 1_Submit_Claim.py            # Claim submission UI + Developer Options
│   │   ├── 2_Review_Decisions.py        # Decision database + trace viewer
│   │   └── 3_Run_Eval.py               # Evaluation runner
│   ├── agents/
│   │   ├── input_validator.py           # Agent 1 — metadata validation
│   │   ├── document_gatekeeper.py       # Agent 2 — document type, quality, consistency
│   │   ├── data_extractor.py            # Agent 3 — structured data OCR extraction
│   │   ├── policy_evaluator.py          # Agent 4 — hybrid policy engine
│   │   ├── fraud_detector.py            # Agent 5 — frequency pattern detection
│   │   └── decision_aggregator.py       # Agent 6 — verdict aggregation + trace builder
│   ├── orchestrator/
│   │   └── pipeline.py                  # Sequences agents with graceful exception handling
│   ├── models/                          # Pydantic models (claim, document, policy, decision, trace)
│   ├── services/                        # Gemini client, policy loader, SQLite manager
│   ├── rules/                           # Sub-limit caps, co-pays, exclusions rules
│   └── utils/                           # Fuzzy string matchers & date arithmetic
├── data/
│   └── test_suite/
│       └── test_suite_guide.md          # Manual UI testing instructions
├── eval/
│   ├── run_eval.py                      # Batch runner for the 12 evaluation test cases
│   ├── eval_report.md                   # Generated results report
│   └── generate_mock_docs.py            # PDF generator for mock medical assets
├── docs/
│   ├── HLD.md                           # High Level Design (architecture, workflows, pipelines)
│   └── LLD.md                           # Low Level Design (models, interfaces, schemas)
├── policy_terms.json                    # Active policy definitions configuration
└── requirements.txt                     # Application dependencies
```

---

## 📖 Design Documentation
Detailed architectural and system specifications can be found under the [docs/](file:///Users/yashrajput/Desktop/PlumAssignment/docs) directory:
* **[High Level Design (HLD)](file:///Users/yashrajput/Desktop/PlumAssignment/docs/HLD.md)** - Details architectural blueprints, agent orchestration workflows, and data pipelines.
* **[Low Level Design (LLD)](file:///Users/yashrajput/Desktop/PlumAssignment/docs/LLD.md)** - Details database schemas, agent API prompt specs, and class designs.

---

## 🔮 Scaling to 10x (Future Scope)

To scale this system to production grade (handling 100k+ claims/day) and optimize performance:

### 1. Production Deployment & High Scalability
* **Asynchronous Queue-Based Processing:** Instead of synchronous HTTP processing in the Streamlit UI, claims will be placed into a message broker like **RabbitMQ** or **AWS SQS**. Worker nodes running the pipeline will consume claims off the queue, preventing thread starvation and allowing the system to handle huge peaks of claim arrivals.
* **Database Scaling:** Migrate from local SQLite to **PostgreSQL on Amazon RDS** with read-replicas. Claims history lookups and fraud checks will query read-replicas, while write operations write to the primary DB.
* **Microservices Orchestration:** Split each agent (Gatekeeper, Data Extractor, Policy Evaluator) into separate stateless microservices packaged in **Docker containers** and deployed on **Kubernetes (EKS/GKE)**. Each microservice can scale independently using Horizontal Pod Autoscalers (HPA) based on queue lengths.

### 2. High Reliability & Fault Tolerance
* **Multi-LLM Redundancy:** Avoid vendor lock-in and single-point-of-failure issues. If the primary Gemini model encounters 429 rate limits or outages, the orchestrator will instantly fall back to secondary models (like Anthropic Claude or OpenAI GPT-4o-mini) to maintain high availability.
* **OpenTelemetry Logging & Observability:** Implement tracing spans for all agents and log data to APM tools like **Datadog** or **Prometheus/Grafana**. This allows tracking:
  * **P99 Latency** per pipeline step.
  * **Token consumption rates** and error traces.
  * **Accuracy drift** of the OCR models over time.

### 3. Reducing Cost Per Claim (Token Optimization)
* **Local Pre-Filters:** Maintain the deterministic **Input Validator** as the entry gate. Invalid claims (e.g. past deadline or not on the roster) are terminated at zero token cost before invoking LLMs.
* **LLM Input Caching & Document Hashing:** Calculate MD5 hashes of uploaded documents. If the same document is uploaded again, fetch OCR and classification results from an **Elasticache (Redis)** cache instead of calling the Gemini Vision API again.
* **Hierarchical Model Routing:**
  * Use cheaper, lightweight models (like Llama-3-8B or Mistral-7B hosted locally on vLLM, costing ~10x less) for simple tasks like Document Classification (Gatekeeper) and plain text extraction.
  * Use advanced models (like Gemini 1.5 Pro) only when the Policy Evaluator encounters complex, multi-page, or highly ambiguous clinical summaries.
* **Prompt Engineering Optimization:** Trim system prompts to use minimalist JSON output schemas and compress context formatting to minimize input token size.
