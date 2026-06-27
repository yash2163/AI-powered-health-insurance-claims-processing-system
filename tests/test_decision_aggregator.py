from datetime import date
from app.agents.decision_aggregator import DecisionAggregator
from app.models.claim import ClaimSubmission
from app.models.decision import PolicyEvaluationResult, FraudCheckResult, Deduction, LineItemDecision
from app.models.enums import ClaimCategory, DecisionVerdict, RejectionReason

def test_decision_aggregator_approved():
    claim = ClaimSubmission(
        member_id="EMP001",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=1500.0,
        documents=[]
    )
    
    policy_result = PolicyEvaluationResult(
        all_checks_passed=True,
        final_approved_amount=1350.0,
        deductions=[Deduction(deduction_type="COPAY", amount=150.0, description="10% copay")]
    )
    
    aggregator = DecisionAggregator()
    decision = aggregator.process(claim, policy_result, None, [], [])
    
    assert decision.decision == DecisionVerdict.APPROVED.value
    assert decision.approved_amount == 1350.0
    assert decision.confidence_score == 0.95
    assert "approved" in decision.message.lower()

def test_decision_aggregator_rejected():
    claim = ClaimSubmission(
        member_id="EMP001",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=3000.0,
        documents=[]
    )
    
    policy_result = PolicyEvaluationResult(
        all_checks_passed=False,
        rejection_reasons=[RejectionReason.WAITING_PERIOD],
        rejection_details=["Treatment is within waiting period."]
    )
    
    aggregator = DecisionAggregator()
    decision = aggregator.process(claim, policy_result, None, [], [])
    
    assert decision.decision == DecisionVerdict.REJECTED.value
    assert decision.approved_amount == 0.0
    assert "rejected" in decision.message.lower()

def test_decision_aggregator_partial():
    claim = ClaimSubmission(
        member_id="EMP001",
        claim_category=ClaimCategory.DENTAL,
        treatment_date=date(2024, 11, 1),
        claimed_amount=12000.0,
        documents=[]
    )
    
    policy_result = PolicyEvaluationResult(
        all_checks_passed=True,
        final_approved_amount=8000.0,
        is_partial=True,
        approved_line_items=[{"description": "Root Canal", "amount": 8000.0}],
        excluded_line_items=[{"description": "Whitening", "amount": 4000.0, "reason": "Cosmetic"}]
    )
    
    aggregator = DecisionAggregator()
    decision = aggregator.process(claim, policy_result, None, [], [])
    
    assert decision.decision == DecisionVerdict.PARTIAL.value
    assert decision.approved_amount == 8000.0

def test_decision_aggregator_component_failure():
    claim = ClaimSubmission(
        member_id="EMP001",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=1500.0,
        documents=[]
    )
    
    policy_result = PolicyEvaluationResult(
        all_checks_passed=True,
        final_approved_amount=1500.0
    )
    
    aggregator = DecisionAggregator()
    decision = aggregator.process(claim, policy_result, None, [], ["fraud_detection"])
    
    # Graceful degradation reduces confidence by 0.30
    assert decision.decision == DecisionVerdict.APPROVED.value
    assert decision.confidence_score == 0.65
    assert "component failure" in decision.message.lower()
