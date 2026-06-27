from datetime import date
from app.agents.data_extractor import DataExtractor
from app.models.claim import ClaimSubmission, ClaimDocument
from app.models.document import DocumentClassification
from app.models.enums import ClaimCategory, DocumentType, DocumentQuality

def test_data_extractor_test_mode(policy_config):
    claim = ClaimSubmission(
        member_id="EMP001",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=1500.0,
        documents=[
            ClaimDocument(
                file_id="F1",
                file_name="prescription.jpg",
                actual_type="PRESCRIPTION",
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
    
    classifications = [
        DocumentClassification(file_id="F1", detected_type=DocumentType.PRESCRIPTION, quality=DocumentQuality.GOOD, confidence=1.0),
        DocumentClassification(file_id="F2", detected_type=DocumentType.HOSPITAL_BILL, quality=DocumentQuality.GOOD, confidence=1.0)
    ]
    
    extractor = DataExtractor()
    extracted, trace = extractor.process(claim, classifications)
    
    assert extracted.primary_diagnosis == "Viral Fever"
    assert extracted.doctor_name == "Dr. Arun Sharma"
    assert extracted.doctor_registration == "KA/45678/2015"
    assert extracted.hospital_name == "City Clinic"
    assert len(extracted.line_items) == 2
    assert extracted.total_extracted_amount == 1500.0
    assert trace.status.value == "PASSED"
