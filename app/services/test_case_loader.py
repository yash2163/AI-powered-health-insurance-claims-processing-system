import json
from datetime import date
from typing import List, Dict, Any

from app.models.claim import ClaimSubmission, ClaimDocument, ClaimHistoryEntry
from app.models.trace import ClaimDecision
from app.models.enums import ClaimCategory

def load_test_cases(filepath: str) -> List[Dict[str, Any]]:
    """Load raw test case dicts from JSON."""
    with open(filepath, "r") as f:
        data = json.load(f)
    return data.get("test_cases", [])

def test_case_to_claim(tc: Dict[str, Any]) -> ClaimSubmission:
    """Convert test case dict to ClaimSubmission model."""
    input_data = tc["input"]
    
    # Map documents
    documents = []
    for doc in input_data.get("documents", []):
        documents.append(ClaimDocument(
            file_id=doc.get("file_id"),
            file_name=doc.get("file_name", doc.get("file_id")),
            actual_type=doc.get("actual_type"),
            quality=doc.get("quality", "GOOD"),
            patient_name_on_doc=doc.get("patient_name_on_doc"),
            content=doc.get("content")
        ))
        
    # Map claims_history
    claims_history = []
    for entry in input_data.get("claims_history", []):
        claims_history.append(ClaimHistoryEntry(
            claim_id=entry.get("claim_id"),
            date=entry.get("date"),
            amount=float(entry.get("amount")),
            provider=entry.get("provider")
        ))
        
    treatment_date = date.fromisoformat(input_data["treatment_date"])
    # Set submission_date equal to treatment_date for historical test cases to pass deadline check
    submission_date = treatment_date
    
    return ClaimSubmission(
        claim_id=tc.get("case_id", "CLM_TEST"),
        member_id=input_data["member_id"],
        policy_id=input_data.get("policy_id", "PLUM_GHI_2024"),
        claim_category=ClaimCategory(input_data["claim_category"]),
        treatment_date=treatment_date,
        claimed_amount=float(input_data["claimed_amount"]),
        hospital_name=input_data.get("hospital_name"),
        documents=documents,
        claims_history=claims_history if claims_history else None,
        ytd_claims_amount=input_data.get("ytd_claims_amount"),
        simulate_component_failure=input_data.get("simulate_component_failure", False),
        pre_auth_approved=input_data.get("pre_auth_approved", False),
        submission_date=submission_date
    )

def evaluate_result(tc: Dict[str, Any], result: Any) -> Dict[str, Any]:
    """Evaluate pipeline result against expected outcome."""
    expected = tc.get("expected", {})
    expected_decision = expected.get("decision")
    
    passed = True
    actual_decision = None
    actual_amount = None
    notes = []
    
    if expected_decision is None:
        # Expecting early stop (error)
        if isinstance(result, dict) and result.get("error") is True:
            passed = True
            actual_decision = "STOP (error)"
            notes.append(f"Successfully stopped early. Error: {result.get('message')}")
        else:
            passed = False
            actual_decision = result.decision if hasattr(result, "decision") else "UNKNOWN"
            notes.append("Expected early stop, but claim processing completed.")
    else:
        # Expecting normal decision
        if isinstance(result, dict):
            passed = False
            actual_decision = f"ERROR: {result.get('message')}"
            notes.append("Expected claim decision, but system returned an error.")
        else:
            actual_decision = result.decision
            actual_amount = result.approved_amount
            
            # Compare decision
            if actual_decision != expected_decision:
                passed = False
                notes.append(f"Decision mismatch. Expected: {expected_decision}, Actual: {actual_decision}")
                
            # Compare approved amount if expected_amount is specified
            expected_amount = expected.get("approved_amount")
            if expected_amount is not None:
                if abs((actual_amount or 0.0) - expected_amount) > 0.01:
                    passed = False
                    notes.append(f"Amount mismatch. Expected: ₹{expected_amount:,.2f}, Actual: ₹{actual_amount:,.2f}")
                else:
                    notes.append("Approved amount matches.")
                    
            if passed:
                notes.append("Decision and amount match successfully.")
                
    return {
        "passed": passed,
        "expected_decision": expected_decision or "STOP (error)",
        "expected_amount": expected.get("approved_amount"),
        "actual_decision": actual_decision,
        "actual_amount": actual_amount,
        "notes": "; ".join(notes)
    }
