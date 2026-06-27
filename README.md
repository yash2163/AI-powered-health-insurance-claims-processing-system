# Plum Health Claims Processor

An automated Health Insurance Claims Processing System powered by a Multi-Agent AI Pipeline and deterministic financial engines.

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
This generates mock PDF files under `data/mock_documents/` which can be uploaded in the UI.

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
