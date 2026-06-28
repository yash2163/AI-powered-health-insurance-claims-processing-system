import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import json
import time
import re
from typing import Dict, Any, List

from app.config import (
    GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TIMEOUT,
    GEMINI_MAX_RETRIES, GEMINI_TEMPERATURE
)

class GeminiAPIError(Exception):
    """Raised when Gemini API call fails after retries."""
    pass

# Prompts
CLASSIFY_DOCUMENT_PROMPT = """You are a medical document classifier for Indian health insurance claims.

Analyze this uploaded medical document and provide:
1. Document type classification
2. Quality assessment
3. Patient name extraction

Respond ONLY in JSON with this exact schema:
{
    "document_type": "PRESCRIPTION" | "HOSPITAL_BILL" | "LAB_REPORT" | "PHARMACY_BILL" | "DIAGNOSTIC_REPORT" | "DENTAL_REPORT" | "DISCHARGE_SUMMARY" | "UNKNOWN",
    "quality": "GOOD" | "LOW" | "UNREADABLE",
    "patient_name": "<extracted name or null>",
    "confidence": <float 0.0 to 1.0>,
    "quality_issues": ["<issue1>", "<issue2>"]
}

Document type rules:
- PRESCRIPTION: Has Rx symbol, doctor details, medication list with dosage
- HOSPITAL_BILL: Has hospital name, itemized charges, bill number, total amount
- LAB_REPORT: Has test names, results, reference ranges, lab name
- PHARMACY_BILL: Has drug license, medication list with MRP/batch/expiry
- DIAGNOSTIC_REPORT: Has imaging or diagnostic findings (MRI, CT, X-ray)
- DENTAL_REPORT: Has dental examination findings
- DISCHARGE_SUMMARY: Has admission/discharge dates, treatment summary

Quality rules:
- GOOD: All key fields clearly readable
- LOW: Some text unclear but key fields partially visible
- UNREADABLE: Critical fields cannot be read; document needs re-upload"""

EXTRACT_PRESCRIPTION_PROMPT = """Extract structured data from this Indian medical prescription.

Return ONLY JSON:
{
    "doctor_name": {"value": "<name>", "confidence": <float>},
    "doctor_registration": {"value": "<reg number>", "confidence": <float>},
    "patient_name": {"value": "<name>", "confidence": <float>},
    "patient_age": {"value": "<age>", "confidence": <float>},
    "patient_gender": {"value": "M|F", "confidence": <float>},
    "date": {"value": "YYYY-MM-DD", "confidence": <float>},
    "diagnosis": {"value": "<diagnosis>", "confidence": <float>},
    "treatment": {"value": "<treatment description if stated>", "confidence": <float>},
    "medicines": [{"name": "<name>", "dosage": "<dosage>", "frequency": "<freq>", "duration": "<dur>"}],
    "tests_ordered": {"value": ["<test1>", "<test2>"], "confidence": <float>},
    "hospital_name": {"value": "<clinic/hospital name>", "confidence": <float>}
}

Rules:
- If a field is not visible, set value to null and confidence to 0.0
- For partially readable: confidence 0.3-0.7
- Common abbreviations: HTN=Hypertension, T2DM=Type 2 Diabetes, URI=Upper Respiratory Infection
- Doctor registration format: STATE/XXXXX/YYYY or AYUR/STATE/XXXXX/YYYY
- Convert all dates to YYYY-MM-DD format"""

EXTRACT_BILL_PROMPT = """Extract structured data from this Indian hospital/clinic/pharmacy bill.

Return ONLY JSON:
{
    "hospital_name": {"value": "<name>", "confidence": <float>},
    "bill_number": {"value": "<number>", "confidence": <float>},
    "date": {"value": "YYYY-MM-DD", "confidence": <float>},
    "patient_name": {"value": "<name>", "confidence": <float>},
    "line_items": [
        {"description": "<item description>", "amount": <float>}
    ],
    "subtotal": {"value": <float>, "confidence": <float>},
    "gst": {"value": <float>, "confidence": <float>},
    "total_amount": {"value": <float>, "confidence": <float>},
    "payment_mode": {"value": "<mode>", "confidence": <float>}
}

Rules:
- Extract EVERY line item with its exact amount
- If amounts are written in words and figures, use the figure
- Flag any corrections/strikethroughs in warnings
- total_amount is the final payable amount"""

EXTRACT_LAB_REPORT_PROMPT = """Extract structured data from this Indian diagnostic/lab report.

Return ONLY JSON:
{
    "lab_name": {"value": "<name>", "confidence": <float>},
    "patient_name": {"value": "<name>", "confidence": <float>},
    "referring_doctor": {"value": "<name>", "confidence": <float>},
    "sample_date": {"value": "YYYY-MM-DD", "confidence": <float>},
    "report_date": {"value": "YYYY-MM-DD", "confidence": <float>},
    "tests": [
        {"name": "<test name>", "result": "<result>", "unit": "<unit>", "normal_range": "<normal range>"}
    ],
    "pathologist_name": {"value": "<name>", "confidence": <float>},
    "remarks": {"value": "<remarks>", "confidence": <float>}
}

Rules:
- Extract all test names and results
- If a field is not present, set value to null and confidence to 0.0"""

POLICY_CLASSIFY_PROMPT = """You are an insurance policy evaluator. Classify the medical claim data against policy terms.

CLAIM DATA:
- Diagnosis: {diagnosis}
- Treatment: {treatment}
- Line items: {line_items_json}
- Claim category: {category}

POLICY EXCLUSIONS:
{exclusions_json}

CATEGORY-SPECIFIC PROCEDURES:
Covered: {covered_procedures_json}
Excluded: {excluded_procedures_json}

WAITING PERIOD CONDITIONS (condition_name: days):
{waiting_conditions_json}

PRE-AUTHORIZATION REQUIREMENTS:
{preauth_requirements_json}

Return ONLY JSON:
{{
    "exclusion_matches": [
        {{
            "item": "<what matched>",
            "matched_exclusion": "<which exclusion it matches>",
            "confidence": <float>,
            "reasoning": "<why this is a match>"
        }}
    ],
    "waiting_period_condition": {{
        "matched_condition": "<condition_key from waiting periods or null>",
        "confidence": <float>,
        "reasoning": "<why this diagnosis maps to this condition>"
    }},
    "line_item_classifications": [
        {{
            "description": "<line item text>",
            "amount": <float>,
            "is_covered": <boolean>,
            "matched_rule": "<which covered/excluded rule it matches or null>",
            "confidence": <float>,
            "reasoning": "<why covered or excluded>"
        }}
    ],
    "requires_pre_authorization": {{
        "required": <boolean>,
        "reason": "<which pre-auth rule applies or null>",
        "confidence": <float>
    }}
}}

IMPORTANT:
- Match semantically, not just by exact string. "Bariatric Consultation" relates to "Bariatric surgery" exclusion.
- "Morbid Obesity" + "Diet Plan" relates to "Obesity and weight loss programs" exclusion.
- "Type 2 Diabetes Mellitus" maps to "diabetes" waiting period condition.
- For dental: "Root Canal Treatment" is in covered list; "Teeth Whitening" is in excluded list.
- For pre-auth: detect if treatment involves MRI, CT Scan, or PET Scan.
- Be conservative: if unsure, set confidence lower and let the system handle it."""

class GeminiClient:
    def __init__(self, api_key: str = None, model_name: str = None):
        key = api_key or GEMINI_API_KEY
        model = model_name or GEMINI_MODEL
        if not key:
            raise ValueError("GEMINI_API_KEY is not configured in the environment.")
        genai.configure(api_key=key)
        self.model = genai.GenerativeModel(
            model_name=model,
            generation_config=GenerationConfig(
                temperature=GEMINI_TEMPERATURE,
                response_mime_type="application/json"
            )
        )

    def _call_with_retry(self, contents: List[Any], timeout: int = None) -> Dict[str, Any]:
        timeout = timeout or GEMINI_TIMEOUT
        last_error = None

        for attempt in range(GEMINI_MAX_RETRIES + 1):
            try:
                response = self.model.generate_content(
                    contents,
                    request_options={"timeout": timeout}
                )
                text = response.text.strip()
                # Strip markdown code fences if present
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()
                return json.loads(text)
            except json.JSONDecodeError as e:
                last_error = GeminiAPIError(f"Invalid JSON response: {e}")
            except Exception as e:
                last_error = GeminiAPIError(f"Gemini API error: {e}")

            if attempt < GEMINI_MAX_RETRIES:
                time.sleep(1)  # Brief delay before retry

        raise last_error

    def classify_document(self, image_data: bytes, content_type: str) -> Dict[str, Any]:
        """Classify document type, quality, and extract patient name."""
        image_part = {
            "mime_type": content_type,
            "data": image_data
        }
        contents = [image_part, CLASSIFY_DOCUMENT_PROMPT]
        return self._call_with_retry(contents)

    def extract_document_data(self, image_data: bytes, content_type: str, doc_type: str) -> Dict[str, Any]:
        """Extract structured data from a document."""
        image_part = {
            "mime_type": content_type,
            "data": image_data
        }
        
        if doc_type == "PRESCRIPTION":
            prompt = EXTRACT_PRESCRIPTION_PROMPT
        elif doc_type in ("HOSPITAL_BILL", "PHARMACY_BILL"):
            prompt = EXTRACT_BILL_PROMPT
        elif doc_type in ("LAB_REPORT", "DIAGNOSTIC_REPORT", "DENTAL_REPORT", "DISCHARGE_SUMMARY"):
            prompt = EXTRACT_LAB_REPORT_PROMPT
        else:
            # General fallback bill extraction
            prompt = EXTRACT_BILL_PROMPT
            
        contents = [image_part, prompt]
        return self._call_with_retry(contents)

    def classify_policy_terms(
        self,
        diagnosis: str,
        treatment: str,
        line_items_json: str,
        category: str,
        exclusions_json: str,
        covered_procedures_json: str,
        excluded_procedures_json: str,
        waiting_conditions_json: str,
        preauth_requirements_json: str
    ) -> Dict[str, Any]:
        """Classify diagnosis/treatment against policy terms. Text only."""
        prompt = POLICY_CLASSIFY_PROMPT.format(
            diagnosis=diagnosis,
            treatment=treatment,
            line_items_json=line_items_json,
            category=category,
            exclusions_json=exclusions_json,
            covered_procedures_json=covered_procedures_json,
            excluded_procedures_json=excluded_procedures_json,
            waiting_conditions_json=waiting_conditions_json,
            preauth_requirements_json=preauth_requirements_json
        )
        return self._call_with_retry([prompt])
