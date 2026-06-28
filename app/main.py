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

# Auto-generate mock documents if they are missing (crucial for cloud deployments where PDFs are gitignored)
test_docs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/test_suite"))
if not os.path.exists(test_docs_dir) or not any(f.endswith(".pdf") for f in os.listdir(test_docs_dir) if os.path.isfile(os.path.join(test_docs_dir, f))):
    try:
        from eval.generate_mock_docs import generate_all_test_docs
        test_cases_json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../test_cases.json"))
        generate_all_test_docs(test_cases_json_path, test_docs_dir)
    except Exception as e:
        st.warning(f"Could not auto-generate mock documents: {e}")

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

from app.utils.ui_components import render_gemini_config_sidebar
render_gemini_config_sidebar()

# Main Landing Page Content
st.markdown("<h1 class='main-title'>🏥 Plum AI Claims Engine</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>Production-Grade Health Insurance Claims Automation Powered by Multi-Agent AI & Hybrid Policy Engines</p>", unsafe_allow_html=True)

if "policy" in st.session_state:
    p = st.session_state.policy
    
    # Create Tabs
    tab1, tab2, tab3 = st.tabs(["🏠 Policy Overview", "🏗️ System Architecture & Guide", "🧪 Test Suite UI Guide"])
    
    with tab1:
        st.markdown("### Active Insurance Policy Terms")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-value'>{p.insurer}</div>
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
        
        # Policy metadata
        left_col, right_col = st.columns([2, 1])
        with left_col:
            st.markdown("#### Policy Rules & Sub-Limits")
            st.write(f"**Policy Holder (Employer):** {p.company_name}")
            st.write(f"**Policy Period:** `{p.policy_start_date}` to `{p.policy_end_date}`")
            st.write(f"**Minimum Allowed Claim Amount:** ₹{p.submission_rules.get('minimum_claim_amount', 500)}")
            st.write(f"**Submission Deadline:** Within {p.submission_rules.get('deadline_days_from_treatment', 30)} days of treatment")
            
        with right_col:
            st.markdown("#### Category Coverage & Co-pays")
            for cat, config in p.opd_categories.items():
                coverage_status = "🟢 Covered" if config.covered else "🔴 Excluded"
                st.write(f"- **{cat.replace('_', ' ').title()}**: {coverage_status} (Cap: ₹{config.sub_limit:,.0f}, Co-pay: {config.copay_percent}%)")

    with tab2:
        st.markdown("### 🏗️ Architectural Blueprint")
        st.markdown("""
        The system relies on a **sequential multi-agent pipeline** orchestrating specialized AI agents alongside a deterministic financial engine. 
        Each claim submission flows through six pipeline stages:
        """)
        
        # Architectural details
        st.markdown("""
        #### 1. Input Validator (Deterministic Agent)
        * **How it works:** Instantly audits submission metadata against policy boundaries.
        * **Rules Checked:**
          * Member ID must exist in the active policy member roster.
          * Treatment date must lie within the policy start/end dates.
          * Treatment date cannot exceed the submission deadline (30 days prior).
          * Claimed amount must be greater than the minimum limit (₹500).
          * Claim category must be active/covered in the policy terms.
        * **Bad Input Behavior:** Stops execution immediately with a detailed error trace, preventing downstream LLM token costs.

        #### 2. Document Gatekeeper (LLM/Vision Agent)
        * **How it works:** Processes uploaded files (`.pdf`, `.png`, `.jpg`) using Gemini vision features or filename keyword fallback rules.
        * **Rules Checked:**
          * **Document Classification:** Identifies document types (Prescriptions, Bills, Lab Reports) to verify if the required set of documents is present for the claim category.
          * **Quality Gate:** Flags unreadable, low-contrast, or corrupted uploads.
          * **Patient Name Consistency:** Uses fuzzy string matching to ensure patient names on all documents match each other and the member roster.
        * **Bad Input Behavior:** If documents belong to different patients (fuzzy score < 0.90) or required files are missing, it throws a validation error and halts processing.

        #### 3. Data Extractor (LLM/Vision Agent)
        * **How it works:** Performs OCR on unstructured invoices, receipts, and hand-written prescriptions to extract structured JSON data.
        * **Data Extracted:** Primary diagnosis, doctor registration details, hospital name, and itemized line-item lists containing service descriptions and cost amounts.

        #### 4. Policy Evaluator (Hybrid Rules Engine)
        * **How it works:** Evaluates the extracted medical data against active policy clauses.
        * **Rules Checked:**
          * **Exclusion Check:** Scans itemized descriptions for cosmetic, dental, or excluded treatments (e.g. teeth whitening, bariatric consultation).
          * **Waiting Period:** Checks if the diagnosis relates to pre-existing conditions subject to a waiting period relative to the member's joining date.
          * **Network Discounts:** Automatically applies pre-negotiated provider discounts (e.g., 15% discount for network hospitals like Apollo).
          * **Co-pays & Caps:** Calculates co-pays and caps the claim against category sub-limits.

        #### 5. Fraud Detector (Deterministic Agent)
        * **How it works:** Analyzes the database for anomalous submission behaviors.
        * **Rules Checked:**
          * **Frequency limits:** Maximum of 2 claims per member per day, and 6 claims per member per month.
          * **High-value limits:** Flags claims above ₹25,000 for manual review.

        #### 6. Decision Aggregator (Deterministic Agent)
        * **How it works:** Aggregates findings from all agents, calculates a confidence score (penalizing low-quality scans or component failures), and compiles the final verdict (`APPROVED`, `PARTIAL`, `REJECTED`, or `MANUAL_REVIEW`) along with a full audit log.
        """)

    with tab3:
        st.markdown("### 🧪 Predefined Test Cases Guide")
        st.markdown("Use this reference sheet to test the 12 evaluation scenarios manually in the UI:")
        
        # Test cases table / markdown
        st.markdown("""
        | Case ID | Test Case Name | Member ID | Category | Amount (₹) | Date | Files to Upload | Expected Verdict | Key Logic Triggered |
        | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: | :--- |
        | **TC001** | Wrong Document Uploaded | `EMP001` | CONSULTATION | 1,500 | `2024-11-01` | `dr_sharma_prescription.pdf`, `another_prescription.pdf` | 🔴 **STOP** | Missing required hospital bill document. |
        | **TC002** | Unreadable Document | `EMP004` | CONSULTATION | 800 | `2024-10-25` | `prescription.pdf`, `blurry_bill.pdf` | 🔴 **STOP** | Document gatekeeper flags bill quality as UNREADABLE. |
        | **TC003** | Different Patient Documents | `EMP001` | CONSULTATION | 1,500 | `2024-11-01` | `prescription_rajesh.pdf`, `bill_arjun.pdf` | 🔴 **STOP** | Patient mismatch: Rajesh Kumar vs Arjun Sharma. |
        | **TC004** | Clean Consultation | `EMP001` | CONSULTATION | 1,500 | `2024-11-01` | `F007.pdf`, `F008.pdf` | 🟢 **APPROVED** (₹1,350) | 10% co-pay deduction on ₹1,500. |
        | **TC005** | Waiting Period — Diabetes | `EMP005` | CONSULTATION | 3,000 | `2024-10-15` | `F009.pdf`, `F010.pdf` | 🔴 **REJECTED** | Diabetes treatment within the initial 90-day waiting period. |
        | **TC006** | Dental Partial Approval | `EMP002` | DENTAL | 12,000 | `2024-10-15` | `F011.pdf` | 🟡 **PARTIAL** (₹8,000) | whitening (₹4,000) excluded as cosmetic; approved Root Canal (₹8,000). |
        | **TC007** | MRI without Pre-Auth | `EMP007` | DIAGNOSTIC | 15,000 | `2024-11-02` | `F012.pdf`, `F013.pdf`, `F014.pdf` | 🔴 **REJECTED** | MRI scan costing > ₹10,000 requires pre-authorization. |
        | **TC008** | Per-Claim Limit / YTD Exceeded | `EMP003` | VISION | 7,500 | `2024-10-20` | `F015.pdf`, `F016.pdf` <br>*(Set **Simulate YTD Claims** = `10000.00`)* | 🔴 **REJECTED** | Claim exceeds the category sub-limit or caps to 0 due to YTD limit exhaustion. |
        | **TC009** | Fraud — Same-Day Claims | `EMP008` | CONSULTATION | 4,800 | `2024-10-30` | `F017.pdf`, `F018.pdf` <br>*(Set **Simulate Prior Claims Today** = `3`)* | 🔵 **MANUAL** | Triggered same-day limit check (4/2 claims submitted today). |
        | **TC010** | Network Hospital Discount | `EMP010` | CONSULTATION | 4,500 | `2024-11-03` | `F019.pdf`, `F020.pdf` | 🟢 **APPROVED** (₹3,442.50) | 15% Apollo discount applied first, then 10% co-pay. |
        | **TC011** | Graceful Degradation | `EMP006` | CONSULTATION | 4,000 | `2024-10-28` | `F021.pdf`, `F022.pdf` <br>*(Check **Simulate Component Failure**)* | 🟢 **APPROVED** (₹3,600) | Fraud agent fails, but system degrades gracefully. Confidence score falls to 0.65. |
        | **TC012** | Excluded Treatment | `EMP009` | CONSULTATION | 8,000 | `2024-10-18` | `F023.pdf`, `F024.pdf` | 🔴 **REJECTED** | Excluded condition: Cosmetic / Bariatric surgery is fully excluded. |
        """)
        
        st.info("💡 Tip: Use the dynamic 'Developer Options (Simulation)' settings at the bottom of the Submit Claim form to configure historical context for TC008, TC009, and TC011.")
        
        st.markdown("### 📥 Download Mock Medical Documents")
        st.write("To test the claims above manually, you can download all the generated mock PDFs (prescriptions, hospital bills) in a single ZIP file, or select individual files below:")
        
        import zipfile
        import io
        import glob
        
        pdf_files = glob.glob(os.path.join(test_docs_dir, "*.pdf"))
        
        if pdf_files:
            # ZIP in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for fpath in pdf_files:
                    fname = os.path.basename(fpath)
                    zip_file.write(fpath, fname)
            
            st.download_button(
                label="📥 Download All Mock Documents (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="plum_test_documents.zip",
                mime="application/zip",
                type="primary"
            )
            
            st.write("")
            st.markdown("**Download Individual Files:**")
            pdf_files_sorted = sorted(pdf_files, key=lambda x: os.path.basename(x))
            filenames = [os.path.basename(f) for f in pdf_files_sorted]
            
            selected_file = st.selectbox("Select document to download:", options=filenames, key="select_doc_dl")
            if selected_file:
                selected_path = os.path.join(test_docs_dir, selected_file)
                with open(selected_path, "rb") as f:
                    file_bytes = f.read()
                st.download_button(
                    label=f"💾 Download {selected_file}",
                    data=file_bytes,
                    file_name=selected_file,
                    mime="application/pdf",
                    key="dl_single_doc_btn"
                )

else:
    st.warning("Please verify your policy configuration file path.")
