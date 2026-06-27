from datetime import datetime
from collections import Counter
from typing import Tuple, List

from app.models.claim import ClaimSubmission, ClaimDocument
from app.models.document import (
    DocumentClassification, ExtractionResult, ExtractedClaimData,
    ExtractedField, LineItem
)
from app.models.enums import DocumentType, TraceStepStatus
from app.models.trace import TraceStep

class DataExtractor:
    def __init__(self, gemini_client=None):
        self.gemini_client = gemini_client

    def process(
        self,
        claim: ClaimSubmission,
        classifications: List[DocumentClassification]
    ) -> Tuple[ExtractedClaimData, TraceStep]:

        start_time = datetime.utcnow()
        extraction_results = []

        for doc, classification in zip(claim.documents, classifications):
            if doc.content is not None:
                # TEST MODE: map pre-provided content to ExtractionResult
                result = self._extract_from_test_content(doc, classification)
            else:
                # REAL MODE: call Gemini Vision
                result = self._extract_from_image(doc, classification)
            extraction_results.append(result)

        # Aggregate across all documents
        aggregated = self._aggregate(extraction_results, claim)

        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        trace = TraceStep(
            step_name="data_extraction",
            status=TraceStepStatus.PASSED,
            duration_ms=duration,
            details=(
                f"Extracted data from {len(extraction_results)} documents. "
                f"Diagnosis: {aggregated.primary_diagnosis or 'N/A'}. "
                f"Treatment: {aggregated.primary_treatment or 'N/A'}. "
                f"Line items: {len(aggregated.line_items)}. "
                f"Total amount: ₹{aggregated.total_extracted_amount or 0:,.0f}."
            )
        )

        return aggregated, trace

    def _extract_from_test_content(
        self, doc: ClaimDocument, classification: DocumentClassification
    ) -> ExtractionResult:
        """
        Map test case content dict to ExtractionResult.
        """
        content = doc.content or {}
        fields = {}
        line_items = []

        for key, value in content.items():
            if key in ("line_items", "items"):
                for item in value:
                    desc = item.get("description") or item.get("name") or "Medical Item"
                    amt = item.get("amount") or item.get("total") or 0.0
                    # Handle pharmacy items quantity/price if amount not direct
                    if not amt and "quantity" in item and "mrp" in item:
                        amt = float(item["quantity"]) * float(item["mrp"])
                    line_items.append(LineItem(description=desc, amount=float(amt)))
            elif key == "total":
                fields["total_amount"] = ExtractedField(value=value, confidence=0.95)
            else:
                fields[key] = ExtractedField(value=value, confidence=0.95)

        # If it's a bill and we have no line items but we have total, create a single line item
        if classification.detected_type in (DocumentType.HOSPITAL_BILL, DocumentType.PHARMACY_BILL) and not line_items:
            total_val = content.get("total") or content.get("total_amount")
            if total_val:
                line_items.append(LineItem(description="Total bill amount", amount=float(total_val)))

        return ExtractionResult(
            file_id=doc.file_id,
            document_type=classification.detected_type,
            extracted_fields=fields,
            line_items=line_items,
            overall_confidence=0.95,
            warnings=[]
        )

    def _extract_from_image(
        self, doc: ClaimDocument, classification: DocumentClassification
    ) -> ExtractionResult:
        """
        Call Gemini Vision for extraction.
        """
        if not self.gemini_client:
            return ExtractionResult(
                file_id=doc.file_id,
                document_type=classification.detected_type,
                overall_confidence=0.5,
                warnings=["Gemini client not configured; empty extraction"]
            )
            
        result = self.gemini_client.extract_document_data(
            doc.file_data, doc.content_type, classification.detected_type.value
        )
        
        fields = {}
        line_items = []
        for k, v in result.items():
            if k == "line_items":
                for item in v:
                    line_items.append(LineItem(
                        description=item.get("description", "Item"),
                        amount=float(item.get("amount", 0.0))
                    ))
            else:
                fields[k] = ExtractedField(
                    value=v.get("value") if isinstance(v, dict) else v,
                    confidence=v.get("confidence", 0.9) if isinstance(v, dict) else 0.9,
                    warning=v.get("warning") if isinstance(v, dict) else None
                )
                
        return ExtractionResult(
            file_id=doc.file_id,
            document_type=classification.detected_type,
            extracted_fields=fields,
            line_items=line_items,
            overall_confidence=sum(f.confidence for f in fields.values()) / len(fields) if fields else 0.9,
            warnings=[]
        )

    def _aggregate(self, results: List[ExtractionResult], claim: ClaimSubmission) -> ExtractedClaimData:
        """
        Aggregate extraction results across all documents.
        """
        diagnosis = None
        treatment = None
        all_line_items = []
        hospital_name = claim.hospital_name
        doctor_name = None
        doctor_reg = None
        patient_names = []
        total = None

        for r in results:
            fields = r.extracted_fields

            # Extract patient name if present to aggregate later
            if "patient_name" in fields and fields["patient_name"].value:
                patient_names.append(fields["patient_name"].value)

            if r.document_type == DocumentType.PRESCRIPTION:
                if "diagnosis" in fields and fields["diagnosis"].value:
                    diagnosis = fields["diagnosis"].value
                if "treatment" in fields and fields["treatment"].value:
                    treatment = fields["treatment"].value
                if "doctor_name" in fields and fields["doctor_name"].value:
                    doctor_name = fields["doctor_name"].value
                if "doctor_registration" in fields and fields["doctor_registration"].value:
                    doctor_reg = fields["doctor_registration"].value

            if r.document_type in (DocumentType.HOSPITAL_BILL, DocumentType.PHARMACY_BILL):
                all_line_items.extend(r.line_items)
                if "hospital_name" in fields and fields["hospital_name"].value:
                    hospital_name = hospital_name or fields["hospital_name"].value
                elif "pharmacy_name" in fields and fields["pharmacy_name"].value:
                    hospital_name = hospital_name or fields["pharmacy_name"].value
                
                if "total_amount" in fields and fields["total_amount"].value:
                    total = total or fields["total_amount"].value

        # Determine most common patient name
        patient_name = None
        if patient_names:
            patient_name = Counter(patient_names).most_common(1)[0][0]
        elif claim.documents:
            # Fallback to first pre-declared patient name
            for doc in claim.documents:
                if doc.patient_name_on_doc:
                    patient_name = doc.patient_name_on_doc
                    break

        # Total: prefer sum of line items, then extracted total, then claimed amount
        if all_line_items:
            total_sum = sum(item.amount for item in all_line_items)
            # Avoid using 0 if line items exist but sum to 0
            if total_sum > 0:
                total = total_sum
        
        if total is None:
            total = claim.claimed_amount

        return ExtractedClaimData(
            documents=results,
            primary_diagnosis=diagnosis,
            primary_treatment=treatment,
            line_items=all_line_items,
            total_extracted_amount=float(total),
            hospital_name=hospital_name,
            doctor_name=doctor_name,
            doctor_registration=doctor_reg,
            patient_name=patient_name,
        )
