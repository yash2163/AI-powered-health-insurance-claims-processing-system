from datetime import date
from app.orchestrator.pipeline import ClaimsPipeline
from app.models.claim import ClaimSubmission, ClaimDocument
from app.models.enums import ClaimCategory, DecisionVerdict

def test_pipeline_integration_happy_path(policy_config):
    claim = ClaimSubmission(
        member_id="EMP001",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        submission_date=date(2024, 11, 1),
        claimed_amount=1500.0,
        documents=[
            ClaimDocument(
                file_id="F1",
                file_name="prescription.jpg",
                actual_type="PRESCRIPTION",
                quality="GOOD",
                patient_name_on_doc="Rajesh Kumar",
                content={
                    "doctor_name": "Dr. Arun Sharma",
                    "doctor_registration": "KA/45678/2015",
                    "patient_name": "Rajesh Kumar",
                    "diagnosis": "Viral Fever",
                    "medicines": ["Paracetamol 650mg"]
                }
            ),
            ClaimDocument(
                file_id="F2",
                file_name="bill.jpg",
                actual_type="HOSPITAL_BILL",
                quality="GOOD",
                patient_name_on_doc="Rajesh Kumar",
                content={
                    "hospital_name": "City Clinic",
                    "patient_name": "Rajesh Kumar",
                    "line_items": [
                        {"description": "Consultation", "amount": 1000.0},
                        {"description": "CBC Test", "amount": 500.0}
                    ],
                    "total": 1500.0
                }
            )
        ]
    )
    
    pipeline = ClaimsPipeline(policy_config)
    decision = pipeline.process_claim(claim)
    
    assert not isinstance(decision, dict)  # Not an error dict
    assert decision.decision == DecisionVerdict.APPROVED.value
    assert decision.approved_amount == 1350.0  # 1500 - 10% copay
    assert decision.confidence_score == 0.95
    assert len(decision.trace.steps) == 6
    assert len(decision.trace.component_failures) == 0

def test_pipeline_integration_graceful_degradation_tc011(policy_config):
    # TC011: simulate_component_failure = True
    claim = ClaimSubmission(
        member_id="EMP006",
        claim_category=ClaimCategory.ALTERNATIVE_MEDICINE,
        treatment_date=date(2024, 10, 28),
        submission_date=date(2024, 10, 28),
        claimed_amount=4000.0,
        simulate_component_failure=True,
        documents=[
            ClaimDocument(
                file_id="F21",
                actual_type="PRESCRIPTION",
                quality="GOOD",
                patient_name_on_doc="Kavita Nair",
                content={
                    "doctor_name": "Vaidya T. Krishnan",
                    "doctor_registration": "AYUR/KL/2345/2019",
                    "diagnosis": "Chronic Joint Pain",
                    "treatment": "Panchakarma Therapy"
                }
            ),
            ClaimDocument(
                file_id="F22",
                actual_type="HOSPITAL_BILL",
                quality="GOOD",
                patient_name_on_doc="Kavita Nair",
                content={
                    "hospital_name": "Ayur Wellness Centre",
                    "total": 4000.0,
                    "line_items": [
                        {"description": "Panchakarma Therapy (5 sessions)", "amount": 3000.0},
                        {"description": "Consultation", "amount": 1000.0}
                    ]
                }
            )
        ]
    )
    
    pipeline = ClaimsPipeline(policy_config)
    decision = pipeline.process_claim(claim)
    
    assert not isinstance(decision, dict)
    assert decision.decision == DecisionVerdict.APPROVED.value
    assert decision.approved_amount == 4000.0  # Alternative med sublimit is 8000, copay is 0%
    assert decision.confidence_score == 0.65  # 0.95 - 0.30 component failure penalty
    assert len(decision.trace.component_failures) == 1
    assert "fraud_detection" in decision.trace.component_failures
    assert "Component failure occurred" in decision.message
