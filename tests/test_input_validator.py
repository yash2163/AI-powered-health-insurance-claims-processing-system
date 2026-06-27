from datetime import date, timedelta
from app.agents.input_validator import InputValidator
from app.models.claim import ClaimSubmission, ClaimDocument
from app.models.enums import ClaimCategory

def test_valid_claim_validation(policy_config):
    claim = ClaimSubmission(
        member_id="EMP001",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=1500.0,
        submission_date=date(2024, 11, 2),
        documents=[
            ClaimDocument(file_id="F1", file_name="prescription.jpg", actual_type="PRESCRIPTION"),
            ClaimDocument(file_id="F2", file_name="bill.jpg", actual_type="HOSPITAL_BILL")
        ]
    )
    
    validator = InputValidator()
    passed, errors, trace = validator.process(claim, policy_config)
    
    assert passed is True
    assert len(errors) == 0
    assert trace.status.value == "PASSED"

def test_invalid_member_validation(policy_config):
    claim = ClaimSubmission(
        member_id="NON_EXISTENT",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=1500.0,
        submission_date=date(2024, 11, 2),
        documents=[]
    )
    
    validator = InputValidator()
    passed, errors, trace = validator.process(claim, policy_config)
    
    assert passed is False
    assert any("not found in the policy roster" in err for err in errors)
    assert trace.status.value == "FAILED"

def test_expired_policy_date_validation(policy_config):
    # Policy starts 2024-04-01, ends 2025-03-31
    claim = ClaimSubmission(
        member_id="EMP001",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2025, 4, 1),
        claimed_amount=1500.0,
        submission_date=date(2025, 4, 2),
        documents=[]
    )
    
    validator = InputValidator()
    passed, errors, trace = validator.process(claim, policy_config)
    
    assert passed is False
    assert any("outside the policy period" in err for err in errors)

def test_below_minimum_amount_validation(policy_config):
    claim = ClaimSubmission(
        member_id="EMP001",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=400.0,  # Min is 500
        submission_date=date(2024, 11, 2),
        documents=[]
    )
    
    validator = InputValidator()
    passed, errors, trace = validator.process(claim, policy_config)
    
    assert passed is False
    assert any("below the minimum claim amount" in err for err in errors)

def test_past_deadline_validation(policy_config):
    claim = ClaimSubmission(
        member_id="EMP001",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 10, 1),
        claimed_amount=1500.0,
        submission_date=date(2024, 11, 15),  # > 30 days
        documents=[]
    )
    
    validator = InputValidator()
    passed, errors, trace = validator.process(claim, policy_config)
    
    assert passed is False
    assert any("submitted more than" in err for err in errors)
