# Plum Health Claims Processor

An automated Health Insurance Claims Processing System powered by a Multi-Agent AI Pipeline and deterministic financial engines.

## 📖 Design Documentation
Detailed architectural and system specifications can be found under the [docs/](file:///Users/yashrajput/Desktop/PlumAssignment/docs) directory:
* **[High Level Design (HLD)](file:///Users/yashrajput/Desktop/PlumAssignment/docs/HLD.md)** - Details architectural blueprints, agent orchestration workflows, and data pipelines.
* **[Low Level Design (LLD)](file:///Users/yashrajput/Desktop/PlumAssignment/docs/LLD.md)** - Details database schemas, agent API prompt specs, and class designs.

---

## 🚀 Features

1. **Multi-Agent Pipeline:**
   * **Input Validator:** Checks dates, rosters, limits, and deadlines.
   * **Document Gatekeeper:** Vision-based doc classification, quality check, and patient cross-checks.
   * **Data Extractor:** Vision-based prescription, bill, and lab report itemised data parsing.
   * **Policy Evaluator:** Semantic exclusions/waiting checks and deterministic discount/copay/sublimit calculations.
   * **Fraud Detector:** Same-day/monthly claim pattern detection.
   * **Decision Aggregator:** Confidence scoring, final verdict, and audit log trace compiler.
2. **Interactive Streamlit UI:** Submit claims with file uploads, review decision databases, and run evaluation suites directly.
3. **Graceful Degradation:** The pipeline tolerates agent failures and falls back gracefully while lowering the confidence score.

---

## 🛠️ Local Setup and Execution

### 1. Installation
Install the required dependencies using pip:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables (Optional for Real Mode)
To run the system in Real Mode (with active Gemini Vision/Text calls), create a `.env` file in the root directory:
```bash
GEMINI_API_KEY=your_actual_api_key_here
```
If the environment variable is not configured, the system automatically falls back to deterministic rule matching (offline/test mode) and runs all 12 test cases at zero token cost.

### 3. Generate Mock Documents
Generate mock PDF prescriptions, bills, and lab reports matching the 12 evaluation test cases:
```bash
python3 eval/generate_mock_docs.py
```
This generates mock PDF files under `data/test_suite/` which can be uploaded in the UI.

### 4. Run Unit Tests
Run the project's 26 unit tests covering all components and integration flows:
```bash
python3 -m pytest tests/
```

### 5. Run the Evaluation Suite
Execute the 12 evaluation test cases from `test_cases.json` and generate the markdown report:
```bash
python3 eval/run_eval.py
```
The report will be saved at [eval_report.md](file:///Users/yashrajput/Desktop/PlumAssignment/eval/eval_report.md).

### 6. Run the Streamlit Web Application
Launch the interactive dashboard to submit claims and explore audit logs:
```bash
streamlit run app/main.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 🔮 Future Scope: Scalability, Reliability & Cost Optimization

To prepare this system for production scaling (handling 100k+ claims/day), the following architectural enhancements are proposed:

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

