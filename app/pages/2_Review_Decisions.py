import streamlit as st
import os
import sys

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.services.database import get_all_decisions, get_decision, init_db
from app.models.enums import DecisionVerdict

init_db()

if "policy" not in st.session_state:
    from app.config import POLICY_FILE_PATH
    from app.services.policy_loader import load_policy
    try:
        st.session_state.policy = load_policy(POLICY_FILE_PATH)
    except Exception:
        pass

st.title("📋 Review Decisions")
st.write("Browse, filter, and drill down into the explainable audit traces for all processed claims.")

# Retrieve decisions
decisions = get_all_decisions()

if not decisions:
    st.info("No claims have been processed yet. Go to the Submit Claim page to file a claim.")
else:
    # Filter controls
    col1, col2 = st.columns(2)
    
    with col1:
        verdict_filter = st.selectbox(
            "Filter by Decision",
            options=["ALL"] + [v.value for v in DecisionVerdict]
        )
    with col2:
        category_filter = st.selectbox(
            "Filter by Category",
            options=["ALL", "CONSULTATION", "DIAGNOSTIC", "PHARMACY", "DENTAL", "VISION", "ALTERNATIVE_MEDICINE"]
        )
        
    # Apply filters
    filtered_decisions = decisions
    if verdict_filter != "ALL":
        filtered_decisions = [d for d in filtered_decisions if d["decision"] == verdict_filter]
    if category_filter != "ALL":
        filtered_decisions = [d for d in filtered_decisions if d["claim_category"] == category_filter]
        
    st.write(f"Showing {len(filtered_decisions)} claims:")
    
    for dec_summary in filtered_decisions:
        claim_id = dec_summary["claim_id"]
        verdict = dec_summary["decision"]
        claimed = dec_summary["claimed_amount"]
        approved = dec_summary["approved_amount"] or 0.0
        member_id = dec_summary["member_id"]
        category = dec_summary["claim_category"]
        treatment_date = dec_summary["treatment_date"]
        hospital = dec_summary["hospital_name"] or "N/A"
        message = dec_summary["message"]
        created_at = dec_summary["created_at"]
        
        # Color coding summary headers
        verdict_color = "🟢"
        if verdict == "REJECTED":
            verdict_color = "🔴"
        elif verdict == "PARTIAL":
            verdict_color = "🟡"
        elif verdict == "MANUAL_REVIEW":
            verdict_color = "🔵"
            
        with st.container(border=True):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"#### {verdict_color} {verdict} — Claim `{claim_id}`")
                st.write(f"**Member:** `{member_id}` | **Category:** `{category}` | **Treatment Date:** {treatment_date} | **Provider:** {hospital}")
                st.write(f"*{message}*")
            with col_b:
                st.write(f"**Claimed:** ₹{claimed:,.2f}")
                if verdict in ("APPROVED", "PARTIAL"):
                    st.write(f"**Approved:** ₹{approved:,.2f}")
                st.write(f"**Conf Score:** {dec_summary['confidence_score']:.2f}")
                
            # Expand to show audit trace
            with st.expander(f"View Full Audit Trace Logs for `{claim_id}`"):
                # Get full decision trace from database
                full_dec = get_decision(claim_id)
                if full_dec and full_dec.get("trace"):
                    trace = full_dec["trace"]
                    st.markdown("### Agent Steps Trace")
                    for step in trace.get("steps", []):
                        status_val = step.get("status")
                        status_icon = "🟢"
                        if status_val == "FAILED":
                            status_icon = "🔴"
                        elif status_val == "DEGRADED":
                            status_icon = "🟡"
                        elif status_val == "SKIPPED":
                            status_icon = "⚪"
                            
                        st.markdown(f"**{status_icon} {step['step_name'].replace('_', ' ').title()}** ({step.get('duration_ms', 0)}ms)")
                        st.write(step.get("details", ""))
                        st.write("---")
                    
                    if trace.get("component_failures"):
                        st.warning(f"**Component Failures Encountered:** {', '.join(trace['component_failures'])}")
                else:
                    st.warning("Trace details could not be loaded for this claim.")
