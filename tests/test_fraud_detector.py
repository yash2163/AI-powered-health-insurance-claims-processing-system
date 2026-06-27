from datetime import date
from app.agents.fraud_detector import FraudDetector
from app.models.claim import ClaimSubmission, ClaimHistoryEntry
from app.models.enums import ClaimCategory

def test_fraud_detector_no_fraud(policy_config):
    claim = ClaimSubmission(
        member_id="EMP001",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=1500.0,
        claims_history=[],
        documents=[]
    )
    
    detector = FraudDetector()
    result, trace = detector.process(claim, policy_config)
    
    assert result.requires_manual_review is False
    assert len(result.signals) == 0
    assert trace.status.value == "PASSED"

def test_fraud_detector_same_day_limit_tc009(policy_config):
    # TC009: 3 existing same-day claims + this one = 4 same-day claims. Limit is 2.
    claim = ClaimSubmission(
        member_id="EMP008",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 10, 30),
        claimed_amount=4800.0,
        claims_history=[
            ClaimHistoryEntry(claim_id="CLM_0081", date="2024-10-30", amount=1200.0),
            ClaimHistoryEntry(claim_id="CLM_0082", date="2024-10-30", amount=1800.0),
            ClaimHistoryEntry(claim_id="CLM_0083", date="2024-10-30", amount=2100.0)
        ],
        documents=[]
    )
    
    detector = FraudDetector()
    result, trace = detector.process(claim, policy_config)
    
    assert result.requires_manual_review is True
    assert len(result.signals) == 1
    assert result.signals[0].signal_type == "SAME_DAY_CLAIMS"
    assert result.signals[0].current_value == 4
    assert result.signals[0].threshold == 2

def test_fraud_detector_high_value(policy_config):
    # High-value claim threshold is 25,000. Claimed 30,000.
    claim = ClaimSubmission(
        member_id="EMP001",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=30000.0,
        claims_history=[],
        documents=[]
    )
    
    detector = FraudDetector()
    result, trace = detector.process(claim, policy_config)
    
    assert result.requires_manual_review is True
    assert len(result.signals) == 1
    assert result.signals[0].signal_type == "HIGH_VALUE_CLAIM"
    assert result.signals[0].current_value == 30000.0
