from datetime import datetime
from typing import Optional, Tuple

from app.models.claim import ClaimSubmission
from app.models.policy import PolicyConfig
from app.models.document import (
    DocumentVerificationResult, DocumentClassification, DocumentIssue,
    DocumentIssueType
)
from app.models.enums import DocumentType, DocumentQuality, TraceStepStatus
from app.models.trace import TraceStep
from app.services.policy_loader import get_document_requirements
from app.utils.text_matching import names_match

class DocumentGatekeeper:
    def __init__(self, gemini_client=None):
        self.gemini_client = gemini_client

    def process(self, claim: ClaimSubmission, policy: PolicyConfig) -> Tuple[DocumentVerificationResult, TraceStep]:
        start_time = datetime.utcnow()
        classifications = []
        issues = []

        # Phase 1: Classify each document
        for doc in claim.documents:
            if doc.is_test_mode:
                # Use pre-declared metadata
                classification = DocumentClassification(
                    file_id=doc.file_id,
                    file_name=doc.file_name,
                    detected_type=DocumentType(doc.actual_type),
                    quality=DocumentQuality(doc.quality) if doc.quality else DocumentQuality.GOOD,
                    confidence=0.99,
                    patient_name_found=doc.patient_name_on_doc or (
                        doc.content.get("patient_name") if doc.content else None
                    )
                )
            else:
                # Call Gemini Vision for classification
                if not self.gemini_client:
                    # Fallback if no gemini client is configured (e.g. tests)
                    classification = DocumentClassification(
                        file_id=doc.file_id,
                        file_name=doc.file_name,
                        detected_type=DocumentType.UNKNOWN,
                        quality=DocumentQuality.GOOD,
                        confidence=1.0,
                        patient_name_found=None
                    )
                else:
                    result = self.gemini_client.classify_document(doc.file_data, doc.content_type)
                    classification = DocumentClassification(
                        file_id=doc.file_id,
                        file_name=doc.file_name,
                        detected_type=DocumentType(result.get("document_type", "UNKNOWN")),
                        quality=DocumentQuality(result.get("quality", "GOOD")),
                        confidence=result.get("confidence", 0.9),
                        patient_name_found=result.get("patient_name"),
                        quality_issues=result.get("quality_issues", [])
                    )
            classifications.append(classification)

        # Phase 2: Completeness — check required docs
        required = get_document_requirements(policy, claim.claim_category)
        required_types = set(required.get("required", []))
        found_types = {c.detected_type.value for c in classifications}
        missing = required_types - found_types

        if missing:
            found_names = ", ".join(sorted(found_types)) if found_types else "no documents"
            missing_names = ", ".join(sorted(missing))
            error_msg = (
                f"Your {claim.claim_category.value.lower()} claim requires the following documents: "
                f"{', '.join(sorted(required_types))}. "
                f"We found: {found_names}. "
                f"Missing: {missing_names}. "
                f"Please upload your {missing_names.lower().replace('_', ' ')} and resubmit."
            )
            issues.append(DocumentIssue(
                issue_type=DocumentIssueType.MISSING_DOCUMENT,
                description=error_msg,
                details={"required": sorted(required_types), "found": sorted(found_types), "missing": sorted(missing)}
            ))

        # Phase 3: Quality gate — required docs must not be UNREADABLE
        for c in classifications:
            if c.quality == DocumentQuality.UNREADABLE and c.detected_type.value in required_types:
                doc_desc = c.detected_type.value.lower().replace('_', ' ')
                error_msg = (
                    f"Your {doc_desc} "
                    f"({c.file_name or c.file_id}) is not readable. "
                    f"Please re-upload a clearer photo of your {doc_desc}."
                )
                issues.append(DocumentIssue(
                    issue_type=DocumentIssueType.UNREADABLE,
                    description=error_msg,
                    affected_document=c.file_name or c.file_id
                ))

        # Phase 4: Cross-document consistency — patient names must match
        names_found = [
            (c.file_id, c.file_name, c.patient_name_found, c.detected_type.value)
            for c in classifications if c.patient_name_found
        ]
        if len(names_found) >= 2:
            reference_name = names_found[0][2]
            for _, fname, name, dtype in names_found[1:]:
                is_match, score = names_match(reference_name, name)
                if not is_match:
                    ref_dtype_desc = names_found[0][3].lower().replace('_', ' ')
                    curr_dtype_desc = dtype.lower().replace('_', ' ')
                    error_msg = (
                        f"The documents appear to belong to different patients. "
                        f"The {ref_dtype_desc} is for "
                        f"'{names_found[0][2]}' but the {curr_dtype_desc} "
                        f"is for '{name}'. All documents must be for the same patient."
                    )
                    issues.append(DocumentIssue(
                        issue_type=DocumentIssueType.PATIENT_MISMATCH,
                        description=error_msg,
                        details={
                            "names_found": {n[3]: n[2] for n in names_found},
                            "similarity_score": score
                        }
                    ))
                    break  # One mismatch is enough

        # Build result
        has_issues = len(issues) > 0
        status = "FAILED" if has_issues else "PASSED"
        error_message = issues[0].description if issues else None

        result = DocumentVerificationResult(
            status=status,
            classifications=classifications,
            missing_required=sorted(missing) if missing else [],
            issues=issues,
            error_message=error_message
        )

        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        trace = TraceStep(
            step_name="document_verification",
            status=TraceStepStatus.PASSED if not has_issues else TraceStepStatus.FAILED,
            duration_ms=duration,
            details=error_message or (
                f"{len(classifications)} documents classified. "
                f"All required documents present. "
                f"Patient names consistent: '{names_found[0][2] if names_found else 'N/A'}'."
            )
        )

        return result, trace
