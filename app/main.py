import streamlit as st
import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import POLICY_FILE_PATH
from app.services.policy_loader import load_policy
from app.services.database import init_db

# Page Config
st.set_page_config(
    page_title="Plum AI Claims Processing",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Rich Aesthetics)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main-title {
        background: linear-gradient(135deg, #FF5A5F 0%, #a239ca 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }
    
    .subtitle {
        color: #6C757D;
        font-size: 1.25rem;
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
        text-align: center;
        transition: transform 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        border-color: #FF5A5F;
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #FF5A5F;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #ADB5BD;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
</style>
""", unsafe_allow_html=True)

# Cache policy loading
@st.cache_resource
def get_cached_policy():
    return load_policy(POLICY_FILE_PATH)

# Initialize Database
init_db()

# Load policy config into session state
if "policy" not in st.session_state:
    try:
        st.session_state.policy = get_cached_policy()
    except Exception as e:
        st.error(f"Error loading policy configuration: {e}")

# Sidebar Brand
st.sidebar.markdown("<h2 style='color:#FF5A5F; font-weight:800; margin-bottom:0;'>🏥 Plum AI</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='color:#6C757D; font-size:0.85rem; margin-bottom:2rem;'>Next-Gen Claims Engine</p>", unsafe_allow_html=True)

st.sidebar.info("Use the sidebar pages to Submit Claims, Review Decisions, or Run the Evaluation Suite.")

# Main Landing Page Content
st.markdown("<h1 class='main-title'>Automated Health Insurance Claims Processing</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>Powered by Multi-Agent AI Pipelines & Deterministic Financial Engines</p>", unsafe_allow_html=True)

if "policy" in st.session_state:
    p = st.session_state.policy
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-value'>{p.insurer.split()[0]}</div>
            <div class='metric-label'>Insurer Partner</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-value'>₹{p.sum_insured_per_employee:,.0f}</div>
            <div class='metric-label'>Sum Insured (Employee)</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-value'>₹{p.annual_opd_limit:,.0f}</div>
            <div class='metric-label'>Annual OPD Limit</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col4:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-value'>{len(p.members)}</div>
            <div class='metric-label'>Active Roster Members</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.write("")
    st.write("")
    
    # Overview Columns
    left_col, right_col = st.columns([2, 1])
    
    with left_col:
        st.subheader("System Architecture Overview")
        st.markdown("""
        Our automated claims processor sequences six specialised agents in a structured workflow:
        1. **Input Validator (Deterministic):** Evaluates claim metadata, member rosters, and deadlines instantly.
        2. **Document Gatekeeper (LLM/Vision):** Classifies documents, validates image quality, and performs cross-document patient name consistency checks.
        3. **Data Extractor (LLM/Vision):** Parses messy handwritten prescriptions, clinic receipts, and bills into standardised schemas.
        4. **Policy Evaluator (Hybrid):** Applies waits, exclusion conditions, and network discounts, computing exact co-pays and sub-limits.
        5. **Fraud Detector (Deterministic):** Identifies anomalous patterns (e.g. multiple same-day claims or high-value triggers).
        6. **Decision Aggregator (Deterministic):** Assembles verdicts (`APPROVED`, `PARTIAL`, `REJECTED`, `MANUAL_REVIEW`) with an explainable audit trace.
        """)
        
    with right_col:
        st.subheader("Roster and Coverage Details")
        st.write(f"**Policy Holder:** {p.company_name}")
        st.write(f"**Policy Period:** {p.policy_start_date} to {p.policy_end_date}")
        st.write(f"**Minimum Claim Amount:** ₹{p.submission_rules.get('minimum_claim_amount', 500)}")
        st.write(f"**Claim Deadline:** {p.submission_rules.get('deadline_days_from_treatment', 30)} days from treatment date")
        
        st.markdown("**Covered OPD Categories:**")
        for cat, config in p.opd_categories.items():
            coverage_status = "✅ Active" if config.covered else "❌ Excluded"
            st.write(f"- {cat.replace('_', ' ').title()}: {coverage_status} (Cap: ₹{config.sub_limit:,.0f}, Co-pay: {config.copay_percent}%)")
else:
    st.warning("Please verify your policy configuration file path.")
