"""Application-wide constants. Do not hardcode policy values — those come from policy_terms.json."""

import os
from dotenv import load_dotenv

load_dotenv()

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GeminiApiKey")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "1"))
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0"))

# Paths
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/claims.db")
POLICY_FILE_PATH = os.getenv("POLICY_FILE_PATH", "policy_terms.json")
TEST_CASES_PATH = os.getenv("TEST_CASES_PATH", "test_cases.json")

# Confidence scoring
BASE_CONFIDENCE = 0.95
LOW_QUALITY_DOC_PENALTY = 0.10
LOW_FIELD_CONFIDENCE_PENALTY = 0.05
COMPONENT_FAILURE_PENALTY = 0.30
LOW_EXCLUSION_CONFIDENCE_PENALTY = 0.10
FUZZY_NAME_MATCH_PENALTY = 0.05
MIN_CONFIDENCE = 0.10

# Fuzzy matching
NAME_MATCH_THRESHOLD = 0.75  # Levenshtein ratio below this = mismatch
