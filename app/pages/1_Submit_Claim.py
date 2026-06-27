import streamlit as st
from datetime import date, datetime
import os
import sys

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.models.claim import ClaimSubmission, ClaimDocument
from app.models.enums import ClaimCategory, TraceStepStatus
from app.orchestrator.pipeline import ClaimsPipeline
from app.services.database import save_claim, save_decision

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .status-header {
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    .card-approved {
        background-color: rgba(40, 167, 69, 0.1);
        border: 2px solid #28a745;
        border-radius: 12px;
        padding: 1.5rem;
        color: #28a745;
        margin-bottom: 1.5rem;
    }
    .card-partial {
        background-color: rgba(255, 193, 7, 0.1);
        border: 2px solid #ffc107;
        border-radius: 12px;
        padding: 1.5rem;
        color: #ffc107;
        margin-bottom: 1.5rem;
    }
    .card-rejected {
        background-color: rgba(220, 53, 69, 0.1);
        border: 2px solid #dc3545;
        border-radius: 12px;
        padding: 1.5rem;
        color: #dc3545;
        margin-bottom: 1.5rem;
    }
    .card-manual {
        background-color: rgba(0, 123, 255, 0.1);
        border: 2px solid #007bff;
        border-radius: 12px;
        padding: 1.5rem;
        color: #007bff;
        margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏥 Submit Health Claim")
st.write("Submit a claim by entering member details, treatment details, and uploading medical documents.")

if "policy" not in st.session_state:
    from app.config import POLICY_FILE_PATH
    from app.services.policy_loader import load_policy
    from app.services.database import init_db
    init_db()
    try:
        st.session_state.policy = load_policy(POLICY_FILE_PATH)
    except Exception as e:
        st.error(f"Failed to load policy: {e}")

policy = st.session_state.policy

# Interactive Member Search (outside the form so it is responsive)
col_search, col_roster = st.columns([3, 2])
with col_search:
    search_id = st.text_input("Search Member by ID (e.g. EMP001, EMP002)", value="EMP001").strip().upper()
    member_id = None
    if search_id:
        if search_id in policy.members:
            m = policy.members[search_id]
            st.markdown(f"<div style='padding:8px 12px; background-color:rgba(40,167,69,0.1); border-left:4px solid #28a745; border-radius:4px; margin-bottom:15px; color:#28a745;'>🟢 <b>Member Selected:</b> {m.name} ({m.relationship.lower()})</div>", unsafe_allow_html=True)
            member_id = search_id
        else:
            st.markdown("<div style='padding:8px 12px; background-color:rgba(220,53,69,0.1); border-left:4px solid #dc3545; border-radius:4px; margin-bottom:15px; color:#dc3545;'>🔴 <b>Member ID not found</b> in policy roster.</div>", unsafe_allow_html=True)

with col_roster:
    with st.expander("View Active Member Roster List"):
        st.table([{"ID": m.member_id, "Name": m.name, "Relationship": m.relationship} for m in policy.members.values()])

# Form layout
with st.form("submit_claim_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Member ID:** `{member_id or 'NOT SELECTED'}`")
        category_val = st.selectbox(
            "Claim Category", 
            options=[cat.value for cat in ClaimCategory]
        )
        claim_category = ClaimCategory(category_val)
        
        treatment_date = st.date_input("Treatment Date", value=date.today())
            
        with col2:
            claimed_amount = st.number_input("Claimed Amount (₹)", min_value=1.0, value=1500.0, step=100.0)
            hospital_name = st.text_input("Hospital / Clinic Name", value="City Clinic")
            pre_auth_approved = st.checkbox("Obtained Pre-Authorization Approval", value=False)
            
        uploaded_files = st.file_uploader(
            "Upload Medical Documents (Prescriptions, Bills, Lab Reports)", 
            type=["jpg", "png", "pdf"], 
            accept_multiple_files=True
        )
        
        # Simulation flags for developer testing
        with st.expander("Developer Options"):
            simulate_component_failure = st.checkbox("Simulate Component Failure (Fraud Detector exception)", value=False)
            
        submit_button = st.form_submit_button("Submit and Process Claim")
        
    if submit_button:
        if not member_id:
            st.error("Please enter a valid Member ID before submitting.")
        elif not uploaded_files:
            st.error("Please upload at least one document to proceed.")
        else:
            # Map uploaded files to ClaimDocument models
            documents = []
            for uploaded_file in uploaded_files:
                file_bytes = uploaded_file.read()
                documents.append(ClaimDocument(
                    file_id=uploaded_file.name,
                    file_name=uploaded_file.name,
                    file_data=file_bytes,
                    content_type=uploaded_file.type
                ))
                
            # Construct submission
            claim = ClaimSubmission(
                member_id=member_id,
                claim_category=claim_category,
                treatment_date=treatment_date,
                claimed_amount=claimed_amount,
                hospital_name=hospital_name if hospital_name else None,
                documents=documents,
                pre_auth_approved=pre_auth_approved,
                simulate_component_failure=simulate_component_failure,
                submission_date=date.today()
            )
            
            # Save claim to database
            save_claim(claim)
            
            # Run multi-agent pipeline with progress spinner
            st.subheader("Claims Pipeline Execution")
            
            # Initialize Pipeline Orchestrator
            # If GeminiApiKey in env, initialize client, otherwise mock fallback is used in agents
            gemini_client = None
            from app.config import GEMINI_API_KEY
            if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
                try:
                    from app.services.gemini_client import GeminiClient
                    gemini_client = GeminiClient()
                except Exception as e:
                    st.warning(f"Failed to initialize Gemini Client: {e}. Falling back to deterministic rules.")
            
            pipeline = ClaimsPipeline(policy, gemini_client)
            
            with st.spinner("Processing claim through agent steps..."):
                result = pipeline.process_claim(claim)
                
            # Display Results
            if isinstance(result, dict) and result.get("error") is True:
                # Validation or early-stop Document Gatekeeper errors
                st.error(f"Early Stop: {result.get('message')}")
                
                # Show execution trace leading to failure
                st.subheader("Process Trace Logs")
                for step in result.get("trace", []):
                    status_color = "🔴" if step["status"] == "FAILED" else "🟢"
                    with st.expander(f"{status_color} {step['step_name'].replace('_', ' ').title()} ({step['duration_ms']}ms)"):
                        st.write(step["details"])
            else:
                # Normal claim decision returned (approved/partial/rejected/manual_review)
                save_decision(result)
                
                st.write("")
                
                # Verdict card formatting
                verdict = result.decision
                if verdict == "APPROVED":
                    st.markdown(f"""
                    <div class='card-approved'>
                        <h3 style='margin:0;'>✅ Claim Approved</h3>
                        <p style='margin:5px 0 0 0;'><b>Approved Amount:</b> ₹{result.approved_amount:,.2f}</p>
                        <p style='margin:0;'><b>Confidence Score:</b> {result.confidence_score:.2f}</p>
                        <p style='margin:0;'>{result.message}</p>
                    </div>
                    """, unsafe_allow_html=True)
                elif verdict == "PARTIAL":
                    st.markdown(f"""
                    <div class='card-partial'>
                        <h3 style='margin:0;'>⚠️ Claim Partially Approved</h3>
                        <p style='margin:5px 0 0 0;'><b>Approved Amount:</b> ₹{result.approved_amount:,.2f}</p>
                        <p style='margin:0;'><b>Confidence Score:</b> {result.confidence_score:.2f}</p>
                        <p style='margin:0;'>{result.message}</p>
                    </div>
                    """, unsafe_allow_html=True)
                elif verdict == "REJECTED":
                    st.markdown(f"""
                    <div class='card-rejected'>
                        <h3 style='margin:0;'>❌ Claim Rejected</h3>
                        <p style='margin:5px 0 0 0;'><b>Rejection Reasons:</b> {', '.join(result.rejection_reasons)}</p>
                        <p style='margin:0;'><b>Confidence Score:</b> {result.confidence_score:.2f}</p>
                        <p style='margin:0;'>{result.message}</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:  # MANUAL_REVIEW
                    st.markdown(f"""
                    <div class='card-manual'>
                        <h3 style='margin:0;'>🔍 Flagged for Manual Review</h3>
                        <p style='margin:5px 0 0 0;'><b>Confidence Score:</b> {result.confidence_score:.2f}</p>
                        <p style='margin:0;'>{result.message}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                # Full Audit Trace Accordion
                st.subheader("Explainable Audit Trace")
                for step in result.trace.steps:
                    status_val = step.status.value
                    if status_val == "PASSED":
                        status_icon = "🟢"
                    elif status_val == "FAILED":
                        status_icon = "🔴"
                    elif status_val == "DEGRADED":
                        status_icon = "🟡"
                    else:
                        status_icon = "⚪"
                        
                    with st.expander(f"{status_icon} Step: {step.step_name.replace('_', ' ').title()} ({step.duration_ms}ms)"):
                        st.write(step.details)
                        if step.input_summary:
                            st.write("**Step Inputs:**", step.input_summary)
                        if step.output_summary:
                            st.write("**Step Outputs:**", step.output_summary)
