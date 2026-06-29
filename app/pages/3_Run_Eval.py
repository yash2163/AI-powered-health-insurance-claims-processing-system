import streamlit as st
import os
import sys
import json
from datetime import datetime, date

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.config import TEST_CASES_PATH
from app.services.test_case_loader import load_test_cases, test_case_to_claim, evaluate_result
from app.orchestrator.pipeline import ClaimsPipeline

# Auto-initialize policy if missing
if "policy" not in st.session_state:
    from app.config import POLICY_FILE_PATH
    from app.services.policy_loader import load_policy
    from app.services.database import init_db
    init_db()
    try:
        st.session_state.policy = load_policy(POLICY_FILE_PATH)
    except Exception as e:
        st.error(f"Failed to load policy config: {e}")

policy = st.session_state.policy

from app.utils.ui_components import render_gemini_config_sidebar
render_gemini_config_sidebar()

st.title("🧪 Evaluation Runner")
st.write("Upload or paste custom evaluation test scenarios to run them through the claims engine pipeline.")

def validate_custom_test_case(tc: dict) -> list:
    """Validate a custom test case JSON object against schema requirements."""
    errors = []
    
    # 1. Top level keys
    required_keys = ["case_id", "case_name", "description", "input"]
    for k in required_keys:
        if k not in tc:
            errors.append(f"Missing top-level key: '{k}'")
            
    if errors:
        return errors
        
    # 2. Input details
    inp = tc["input"]
    if not isinstance(inp, dict):
        errors.append("'input' must be a JSON object.")
        return errors
        
    input_required = ["member_id", "claim_category", "treatment_date", "claimed_amount"]
    for k in input_required:
        if k not in inp:
            errors.append(f"Missing required key in 'input': '{k}'")
            
    if errors:
        return errors
        
    # 3. Values validation
    # Category
    from app.models.enums import ClaimCategory
    cat_vals = [c.value for c in ClaimCategory]
    if inp["claim_category"] not in cat_vals:
        errors.append(f"Invalid 'claim_category': '{inp['claim_category']}'. Must be one of {cat_vals}")
        
    # Date
    try:
        date.fromisoformat(str(inp["treatment_date"]))
    except ValueError:
        errors.append(f"Invalid 'treatment_date': '{inp['treatment_date']}'. Use YYYY-MM-DD format.")
        
    # Claimed Amount
    try:
        float(inp["claimed_amount"])
    except (ValueError, TypeError):
        errors.append(f"'claimed_amount' must be a number (got {type(inp['claimed_amount']).__name__}).")
        
    # Expected output
    if "expected" in tc:
        exp = tc["expected"]
        if not isinstance(exp, dict):
            errors.append("'expected' must be a JSON object.")
        else:
            if "decision" in exp and exp["decision"] not in ["APPROVED", "PARTIAL", "REJECTED", "MANUAL_REVIEW", None]:
                errors.append(f"Expected 'decision' must be APPROVED, PARTIAL, REJECTED, MANUAL_REVIEW, or null.")
            if "approved_amount" in exp and exp["approved_amount"] is not None:
                try:
                    float(exp["approved_amount"])
                except (ValueError, TypeError):
                    errors.append(f"Expected 'approved_amount' must be a number.")
                    
    # Document attachments
    if "documents" in inp:
        if not isinstance(inp["documents"], list):
            errors.append("'documents' must be a list of objects.")
        else:
            for idx, doc in enumerate(inp["documents"]):
                if not isinstance(doc, dict):
                    errors.append(f"Document at index {idx} must be a JSON object.")
                    continue
                if "file_id" not in doc:
                    errors.append(f"Document at index {idx} is missing 'file_id'.")
                if "actual_type" not in doc:
                    errors.append(f"Document at index {idx} is missing 'actual_type'.")
                else:
                    valid_doc_types = ["PRESCRIPTION", "HOSPITAL_BILL", "PHARMACY_BILL", "LAB_REPORT", "DIAGNOSTIC_REPORT", "DENTAL_REPORT", "DISCHARGE_SUMMARY"]
                    if doc["actual_type"] not in valid_doc_types:
                        errors.append(f"Invalid 'actual_type' in document {idx}: '{doc['actual_type']}'. Must be one of {valid_doc_types}.")
                        
    # Claims history
    if "claims_history" in inp:
        if not isinstance(inp["claims_history"], list):
            errors.append("'claims_history' must be a list of objects.")
        else:
            for idx, entry in enumerate(inp["claims_history"]):
                if not isinstance(entry, dict):
                    errors.append(f"Claims history entry at index {idx} must be a JSON object.")
                    continue
                for k in ["claim_id", "date", "amount"]:
                    if k not in entry:
                        errors.append(f"Claims history entry at index {idx} is missing key: '{k}'")
                if "date" in entry:
                    try:
                        date.fromisoformat(str(entry["date"]))
                    except ValueError:
                        errors.append(f"Invalid date format in claims history index {idx}: '{entry['date']}'. Use YYYY-MM-DD.")
                if "amount" in entry:
                    try:
                        float(entry["amount"])
                    except (ValueError, TypeError):
                        errors.append(f"Invalid amount value in claims history index {idx}.")
                        
    return errors

st.subheader("Run Custom Evaluation Cases")
st.write("Upload a JSON file containing a test case or paste a JSON object to run it through the system.")

# Example Schema Expander
with st.expander("Show Expected JSON Format Template"):
    template = {
        "case_id": "TC_CUSTOM_01",
        "case_name": "Custom Test Case Description",
        "description": "Short explanation of the test scenario",
        "input": {
            "member_id": "EMP001",
            "claim_category": "CONSULTATION",
            "treatment_date": "2024-11-01",
            "claimed_amount": 1500.0,
            "hospital_name": "City Clinic",
            "pre_auth_approved": False,
            "simulate_component_failure": False,
            "ytd_claims_amount": 0.0,
            "claims_history": [],
            "documents": [
                {
                    "file_id": "doc_1",
                    "actual_type": "PRESCRIPTION",
                    "quality": "GOOD",
                    "patient_name_on_doc": "Rajesh Kumar",
                    "content": {
                        "diagnosis": "Viral Fever"
                    }
                }
            ]
        },
        "expected": {
            "decision": "APPROVED",
            "approved_amount": 1350.0
        }
    }
    st.code(json.dumps(template, indent=2), language="json")
    
uploaded_json = st.file_uploader("Upload Test Case JSON file", type=["json"], key="custom_uploader")
pasted_json = st.text_area("Or paste JSON text here:", height=200, placeholder="Paste JSON test case data...", key="custom_text_pasted")

run_custom = st.button("Run Custom Test Case", type="primary", key="run_custom_btn")

if run_custom:
    custom_data = None
    
    # 1. Parse JSON
    if uploaded_json:
        try:
            custom_data = json.loads(uploaded_json.read().decode("utf-8"))
        except Exception as e:
            st.error(f"Error parsing uploaded file: {e}")
    elif pasted_json.strip():
        try:
            custom_data = json.loads(pasted_json)
        except Exception as e:
            st.error(f"Error parsing pasted JSON: {e}")
    else:
        st.warning("Please upload a file or paste a JSON object first.")
        
    if custom_data:
        # Detect list, single dict, or dict containing a 'test_cases' list (like test_cases.json)
        if isinstance(custom_data, dict):
            if "test_cases" in custom_data and isinstance(custom_data["test_cases"], list):
                test_cases_to_run = custom_data["test_cases"]
            else:
                test_cases_to_run = [custom_data]
        elif isinstance(custom_data, list):
            test_cases_to_run = custom_data
        else:
            st.error("JSON must be a test case object or a list of test case objects.")
            test_cases_to_run = []
            
        if test_cases_to_run:
            # 2. Schema Validation
            all_valid = True
            validated_cases = []
            
            for idx, tc in enumerate(test_cases_to_run):
                tc_errors = validate_custom_test_case(tc)
                if tc_errors:
                    all_valid = False
                    st.error(f"Validation failed for test case #{idx+1} ({tc.get('case_id', 'Unknown ID')}):")
                    for err in tc_errors:
                        st.write(f"- ⚠️ {err}")
                else:
                    validated_cases.append(tc)
                    
            # 3. Process claims if all cases are valid
            if all_valid and validated_cases:
                st.success("Schema validation passed! Executing custom claims...")
                from app.utils.ui_components import get_gemini_client
                pipeline = ClaimsPipeline(policy, get_gemini_client())
                
                for tc in validated_cases:
                    case_id = tc["case_id"]
                    case_name = tc["case_name"]
                    st.write(f"Executing `{case_id}: {case_name}`...")
                    
                    claim = test_case_to_claim(tc)
                    result = pipeline.process_claim(claim)
                    
                    eval_res = evaluate_result(tc, result)
                    status_emoji = "✅ PASSED" if eval_res["passed"] else "❌ FAILED"
                    
                    st.markdown(f"### {status_emoji} Result for {case_id}")
                    st.write(f"**Expected Decision:** {eval_res['expected_decision']}")
                    st.write(f"**Expected Amount:** ₹{eval_res['expected_amount'] if eval_res['expected_amount'] is not None else '—'}")
                    st.write(f"**Actual Decision:** {eval_res['actual_decision']}")
                    st.write(f"**Actual Amount:** ₹{eval_res['actual_amount'] if eval_res['actual_amount'] is not None else '—'}")
                    st.write(f"**Notes:** {eval_res['notes']}")
                    
                    # Trace expandable logs
                    trace_steps = result.get("trace") if isinstance(result, dict) else [s.model_dump() for s in result.trace.steps]
                    with st.expander("View Execution Trace Steps"):
                        for step in trace_steps:
                            step_status = step.get("status")
                            step_icon = "🟢"
                            if step_status == "FAILED":
                                step_icon = "🔴"
                            elif step_status == "DEGRADED":
                                step_icon = "🟡"
                            st.write(f"- {step_icon} **{step['step_name'].replace('_', ' ').title()}** ({step.get('duration_ms', 0)}ms): {step.get('details', '')}")
                        st.write("---")
