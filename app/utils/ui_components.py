import streamlit as st
import google.generativeai as genai

def render_gemini_config_sidebar():
    st.sidebar.markdown("---")
    st.sidebar.markdown("<h3 style='color:#FF5A5F; font-weight:700; margin-bottom:0.5rem;'>🔑 Gemini API Configuration</h3>", unsafe_allow_html=True)

    # Initialize session states from environment if not present
    if "gemini_api_key" not in st.session_state:
        from app.config import GEMINI_API_KEY
        st.session_state.gemini_api_key = GEMINI_API_KEY or ""
    if "gemini_model" not in st.session_state:
        from app.config import GEMINI_MODEL
        st.session_state.gemini_model = GEMINI_MODEL or "gemini-2.5-flash"
    if "api_key_valid" not in st.session_state:
        # If API key is present in env, validate it on start
        if st.session_state.gemini_api_key:
            try:
                genai.configure(api_key=st.session_state.gemini_api_key)
                model = genai.GenerativeModel(st.session_state.gemini_model)
                model.generate_content("Say Hello")
                st.session_state.api_key_valid = True
            except Exception:
                st.session_state.api_key_valid = False
        else:
            st.session_state.api_key_valid = False

    # Input fields
    api_key_input = st.sidebar.text_input(
        "Gemini API Key",
        value=st.session_state.gemini_api_key,
        type="password",
        help="Input your Google AI Studio API key."
    )
    
    model_input = st.sidebar.text_input(
        "Gemini Model Model",
        value=st.session_state.gemini_model,
        help="e.g. gemini-2.5-flash, gemini-3.5-flash"
    )

    # If inputs change, reset validity
    if api_key_input != st.session_state.gemini_api_key or model_input != st.session_state.gemini_model:
        st.session_state.gemini_api_key = api_key_input
        st.session_state.gemini_model = model_input
        st.session_state.api_key_valid = False

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("Validate Key", key="validate_key_btn"):
            if not api_key_input:
                st.sidebar.error("API Key is required!")
            else:
                with st.sidebar.spinner("Validating..."):
                    try:
                        genai.configure(api_key=api_key_input)
                        model = genai.GenerativeModel(model_input)
                        response = model.generate_content("Say Hello")
                        if response.text:
                            st.session_state.api_key_valid = True
                            st.sidebar.success("✅ Model validated!")
                    except Exception as e:
                        st.session_state.api_key_valid = False
                        st.sidebar.error(f"❌ Connection failed: {str(e)}")
                        
    with col2:
        if st.button("Change Key", key="change_key_btn"):
            st.session_state.gemini_api_key = ""
            st.session_state.api_key_valid = False
            st.rerun()

    # Show confirmation status
    if st.session_state.api_key_valid:
        st.sidebar.markdown("<p style='color:#28A745; font-weight:bold; margin-top:0.5rem;'>🟢 Status: Validated & Active</p>", unsafe_allow_html=True)
    else:
        st.sidebar.markdown("<p style='color:#DC3545; font-weight:bold; margin-top:0.5rem;'>🟡 Status: Offline Fallback Mode</p>", unsafe_allow_html=True)

    # Help expander: Instructions on how to get a key
    with st.sidebar.expander("ℹ️ How to get a Gemini API Key?"):
        st.markdown("""
        1. Go to **[Google AI Studio](https://aistudio.google.com/)**.
        2. Sign in with your Google account.
        3. Click **Get API Key** in the top left.
        4. Click **Create API Key**.
        5. Copy the generated key and paste it here.
        """)

    # Fail-safe explanation
    with st.sidebar.expander("⚠️ What if the key doesn't work?"):
        st.markdown("""
        If your API key is invalid, rate-limited, or fails, the claims pipeline will **automatically degrade gracefully** to offline fallback mode.
        
        * **Gatekeeper:** Classifies files deterministically based on filename patterns.
        * **Policy Engine:** Checks for exclusions and waiting periods using fallback dictionary lookups.
        * **Verdict:** Will still process and calculate amounts correctly, but will flag a warning and lower the final confidence score (e.g. `0.65` instead of `0.95`).
        """)

def get_gemini_client():
    if not st.session_state.get("gemini_api_key") or not st.session_state.get("api_key_valid"):
        return None
    try:
        from app.services.gemini_client import GeminiClient
        return GeminiClient(
            api_key=st.session_state.gemini_api_key,
            model_name=st.session_state.gemini_model
        )
    except Exception:
        return None
