from datetime import date
from app.agents.document_gatekeeper import DocumentGatekeeper
from app.models.claim import ClaimSubmission, ClaimDocument
from app.models.enums import ClaimCategory

def test_document_gatekeeper_passed(policy_config):
    claim = ClaimSubmission(
        member_id="EMP001",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=1500.0,
        documents=[
            ClaimDocument(file_id="F1", file_name="prescription.jpg", actual_type="PRESCRIPTION", quality="GOOD", patient_name_on_doc="Rajesh Kumar"),
            ClaimDocument(file_id="F2", file_name="bill.jpg", actual_type="HOSPITAL_BILL", quality="GOOD", patient_name_on_doc="Rajesh Kumar")
        ]
    )
    
    gatekeeper = DocumentGatekeeper()
    result, trace = gatekeeper.process(claim, policy_config)
    
    assert result.status == "PASSED"
    assert len(result.issues) == 0
    assert trace.status.value == "PASSED"

def test_document_gatekeeper_missing_doc(policy_config):
    # TC001: consultation requires PRESCRIPTION and HOSPITAL_BILL. Uploading two prescriptions.
    claim = ClaimSubmission(
        member_id="EMP001",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=1500.0,
        documents=[
            ClaimDocument(file_id="F1", file_name="dr_sharma_prescription.jpg", actual_type="PRESCRIPTION"),
            ClaimDocument(file_id="F2", file_name="another_prescription.jpg", actual_type="PRESCRIPTION")
        ]
    )
    
    gatekeeper = DocumentGatekeeper()
    result, trace = gatekeeper.process(claim, policy_config)
    
    assert result.status == "FAILED"
    assert len(result.issues) == 1
    assert result.issues[0].issue_type.value == "MISSING_DOCUMENT"
    assert "HOSPITAL_BILL" in result.error_message
    assert "PRESCRIPTION" in result.error_message
    assert trace.status.value == "FAILED"

def test_document_gatekeeper_unreadable_doc(policy_config):
    # TC002: pharmacy requires PRESCRIPTION and PHARMACY_BILL. Pharmacy bill is blurry and unreadable.
    claim = ClaimSubmission(
        member_id="EMP004",
        claim_category=ClaimCategory.PHARMACY,
        treatment_date=date(2024, 10, 25),
        claimed_amount=800.0,
        documents=[
            ClaimDocument(file_id="F3", file_name="prescription.jpg", actual_type="PRESCRIPTION", quality="GOOD"),
            ClaimDocument(file_id="F4", file_name="blurry_bill.jpg", actual_type="PHARMACY_BILL", quality="UNREADABLE")
        ]
    )
    
    gatekeeper = DocumentGatekeeper()
    result, trace = gatekeeper.process(claim, policy_config)
    
    assert result.status == "FAILED"
    assert len(result.issues) == 1
    assert result.issues[0].issue_type.value == "UNREADABLE"
    assert "blurry_bill.jpg" in result.error_message
    assert trace.status.value == "FAILED"

def test_document_gatekeeper_name_mismatch(policy_config):
    # TC003: prescription for Rajesh Kumar, bill for Arjun Mehta.
    claim = ClaimSubmission(
        member_id="EMP001",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=1500.0,
        documents=[
            ClaimDocument(file_id="F5", file_name="prescription_rajesh.jpg", actual_type="PRESCRIPTION", patient_name_on_doc="Rajesh Kumar"),
            ClaimDocument(file_id="F6", file_name="bill_arjun.jpg", actual_type="HOSPITAL_BILL", patient_name_on_doc="Arjun Mehta")
        ]
    )
    
    gatekeeper = DocumentGatekeeper()
    result, trace = gatekeeper.process(claim, policy_config)
    
    assert result.status == "FAILED"
    assert len(result.issues) == 1
    assert result.issues[0].issue_type.value == "PATIENT_MISMATCH"
    assert "Rajesh Kumar" in result.error_message
    assert "Arjun Mehta" in result.error_message
    assert trace.status.value == "FAILED"
