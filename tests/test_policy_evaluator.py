from datetime import date
from app.agents.policy_evaluator import PolicyEvaluator
from app.models.claim import ClaimSubmission, ClaimDocument
from app.models.document import ExtractedClaimData, ExtractionResult, ExtractedField, LineItem
from app.models.enums import ClaimCategory, DocumentType, RejectionReason

def test_policy_evaluator_waiting_period_tc005(policy_config):
    # Member joined 2024-09-01. Claim on 2024-10-15 (44 days after join).
    # Diagnosis: Type 2 Diabetes Mellitus. Diabetes has specific waiting period of 90 days.
    claim = ClaimSubmission(
        member_id="EMP005",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 10, 15),
        claimed_amount=3000.0,
        documents=[]
    )
    
    extracted = ExtractedClaimData(
        documents=[],
        primary_diagnosis="Type 2 Diabetes Mellitus",
        line_items=[],
        total_extracted_amount=3000.0
    )
    
    evaluator = PolicyEvaluator()
    result, trace = evaluator.process(claim, extracted, policy_config)
    
    assert result.all_checks_passed is False
    assert RejectionReason.WAITING_PERIOD in result.rejection_reasons
    assert "eligible for diabetes-related claims from 2024-11-30" in result.rejection_details[0]
    assert result.final_approved_amount == 0.0

def test_policy_evaluator_dental_partial_tc006(policy_config):
    # Root Canal Treatment (8000) and Teeth Whitening (4000)
    claim = ClaimSubmission(
        member_id="EMP002",
        claim_category=ClaimCategory.DENTAL,
        treatment_date=date(2024, 10, 15),
        claimed_amount=12000.0,
        documents=[]
    )
    
    extracted = ExtractedClaimData(
        documents=[],
        primary_diagnosis="Tooth Pain",
        line_items=[
            LineItem(description="Root Canal Treatment", amount=8000.0),
            LineItem(description="Teeth Whitening", amount=4000.0)
        ],
        total_extracted_amount=12000.0
    )
    
    evaluator = PolicyEvaluator()
    result, trace = evaluator.process(claim, extracted, policy_config)
    
    assert result.all_checks_passed is True
    assert len(result.rejection_reasons) == 0
    assert result.is_partial is True
    assert result.final_approved_amount == 8000.0
    assert len(result.line_item_decisions) == 2
    assert result.line_item_decisions[0].approved is True
    assert result.line_item_decisions[1].approved is False
    assert "Teeth Whitening" in result.line_item_decisions[1].description

def test_policy_evaluator_pre_auth_tc007(policy_config):
    # MRI Lumbar Spine costing ₹15,000 without pre-auth
    claim = ClaimSubmission(
        member_id="EMP007",
        claim_category=ClaimCategory.DIAGNOSTIC,
        treatment_date=date(2024, 11, 2),
        claimed_amount=15000.0,
        documents=[]
    )
    
    extracted = ExtractedClaimData(
        documents=[],
        primary_diagnosis="Suspected Lumbar Disc Herniation",
        line_items=[LineItem(description="MRI Lumbar Spine", amount=15000.0)],
        total_extracted_amount=15000.0
    )
    
    evaluator = PolicyEvaluator()
    result, trace = evaluator.process(claim, extracted, policy_config)
    
    assert result.all_checks_passed is False
    assert RejectionReason.PRE_AUTH_MISSING in result.rejection_reasons
    assert result.final_approved_amount == 0.0

def test_policy_evaluator_pre_auth_approved(policy_config):
    # MRI Lumbar Spine costing ₹15,000 WITH pre-auth
    claim = ClaimSubmission(
        member_id="EMP007",
        claim_category=ClaimCategory.DIAGNOSTIC,
        treatment_date=date(2024, 11, 2),
        claimed_amount=15000.0,
        pre_auth_approved=True,
        documents=[]
    )
    
    extracted = ExtractedClaimData(
        documents=[],
        primary_diagnosis="Suspected Lumbar Disc Herniation",
        line_items=[LineItem(description="MRI Lumbar Spine", amount=15000.0)],
        total_extracted_amount=15000.0
    )
    
    evaluator = PolicyEvaluator()
    result, trace = evaluator.process(claim, extracted, policy_config)
    
    assert result.all_checks_passed is False
    assert RejectionReason.PER_CLAIM_EXCEEDED in result.rejection_reasons

def test_policy_evaluator_per_claim_limit_tc008(policy_config):
    # Claimed amount 7500. Effective cap for Consultation: max(5000, 2000) = 5000.
    claim = ClaimSubmission(
        member_id="EMP003",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 10, 20),
        claimed_amount=7500.0,
        documents=[]
    )
    
    extracted = ExtractedClaimData(
        documents=[],
        primary_diagnosis="Gastroenteritis",
        line_items=[
            LineItem(description="Consultation Fee", amount=2000.0),
            LineItem(description="Medicines", amount=5500.0)
        ],
        total_extracted_amount=7500.0
    )
    
    evaluator = PolicyEvaluator()
    result, trace = evaluator.process(claim, extracted, policy_config)
    
    assert result.all_checks_passed is False
    assert RejectionReason.PER_CLAIM_EXCEEDED in result.rejection_reasons

def test_policy_evaluator_network_discount_tc010(policy_config):
    # Consultation at Apollo Hospitals, claimed amount 4500.
    # 20% discount: 4500 * 0.8 = 3600. 10% copay: 3600 * 0.9 = 3240.
    claim = ClaimSubmission(
        member_id="EMP010",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 3),
        claimed_amount=4500.0,
        hospital_name="Apollo Hospitals",
        documents=[]
    )
    
    extracted = ExtractedClaimData(
        documents=[],
        primary_diagnosis="Acute Bronchitis",
        line_items=[
            LineItem(description="Consultation Fee", amount=1500.0),
            LineItem(description="Medicines", amount=3000.0)
        ],
        total_extracted_amount=4500.0,
        hospital_name="Apollo Hospitals"
    )
    
    evaluator = PolicyEvaluator()
    result, trace = evaluator.process(claim, extracted, policy_config)
    
    assert result.all_checks_passed is True
    assert result.final_approved_amount == 3240.0
    assert len(result.deductions) == 2
    assert result.deductions[0].deduction_type == "NETWORK_DISCOUNT"
    assert result.deductions[0].amount == 900.0
    assert result.deductions[1].deduction_type == "COPAY"
    assert result.deductions[1].amount == 360.0

def test_policy_evaluator_exclusion_tc012(policy_config):
    # Bariatric consultation and diet plan. Obesity is excluded.
    claim = ClaimSubmission(
        member_id="EMP009",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 10, 18),
        claimed_amount=8000.0,
        documents=[]
    )
    
    extracted = ExtractedClaimData(
        documents=[],
        primary_diagnosis="Morbid Obesity — BMI 37",
        line_items=[
            LineItem(description="Bariatric Consultation", amount=3000.0),
            LineItem(description="Personalised Diet and Nutrition Program", amount=5000.0)
        ],
        total_extracted_amount=8000.0
    )
    
    evaluator = PolicyEvaluator()
    result, trace = evaluator.process(claim, extracted, policy_config)
    
    assert result.all_checks_passed is False
    assert RejectionReason.EXCLUDED_CONDITION in result.rejection_reasons
