from datetime import datetime
from typing import Union, Dict, Any

from app.models.claim import ClaimSubmission
from app.models.policy import PolicyConfig
from app.models.document import ExtractedClaimData
from app.models.decision import PolicyEvaluationResult, FraudCheckResult
from app.models.enums import TraceStepStatus, DecisionVerdict
from app.models.trace import ClaimDecision, AuditTrace, TraceStep
from app.agents.input_validator import InputValidator
from app.agents.document_gatekeeper import DocumentGatekeeper
from app.agents.data_extractor import DataExtractor
from app.agents.policy_evaluator import PolicyEvaluator
from app.agents.fraud_detector import FraudDetector
from app.agents.decision_aggregator import DecisionAggregator

class ClaimsPipeline:
    def __init__(self, policy: PolicyConfig, gemini_client=None):
        self.policy = policy
        self.gemini_client = gemini_client
        self.input_validator = InputValidator()
        self.doc_gatekeeper = DocumentGatekeeper(gemini_client)
        self.data_extractor = DataExtractor(gemini_client)
        self.policy_evaluator = PolicyEvaluator(gemini_client)
        self.fraud_detector = FraudDetector()
        self.decision_aggregator = DecisionAggregator()

    def process_claim(self, claim: ClaimSubmission) -> Union[ClaimDecision, Dict[str, Any]]:
        """
        Process a claim through the full pipeline.

        Returns:
            ClaimDecision on success (any verdict including REJECTED).
            dict with {"error": True, "message": str, "trace": [...]} on doc/validation errors.
        """
        trace_steps = []
        component_failures = []

        # Step 1: Input Validation
        passed, errors, trace = self.input_validator.process(claim, self.policy)
        trace_steps.append(trace)
        if not passed:
            return {
                "error": True,
                "error_type": "VALIDATION_ERROR",
                "message": "; ".join(errors),
                "trace": [t.model_dump() for t in trace_steps]
            }

        # Step 2: Document Gatekeeper
        try:
            doc_result, trace = self.doc_gatekeeper.process(claim, self.policy)
            trace_steps.append(trace)
            if doc_result.status == "FAILED":
                return {
                    "error": True,
                    "error_type": "DOCUMENT_ERROR",
                    "message": doc_result.error_message,
                    "issues": [i.model_dump() for i in doc_result.issues],
                    "trace": [t.model_dump() for t in trace_steps]
                }
        except Exception as e:
            trace_steps.append(TraceStep(
                step_name="document_verification",
                status=TraceStepStatus.FAILED,
                details=f"Document verification failed: {str(e)}"
            ))
            component_failures.append("document_verification")
            # Can't continue without document verification
            return {
                "error": True,
                "error_type": "SYSTEM_ERROR",
                "message": "Document verification failed. Please try again.",
                "trace": [t.model_dump() for t in trace_steps]
            }

        # Step 3: Data Extraction
        extracted = None
        try:
            extracted, trace = self.data_extractor.process(claim, doc_result.classifications)
            trace_steps.append(trace)
        except Exception as e:
            trace_steps.append(TraceStep(
                step_name="data_extraction",
                status=TraceStepStatus.FAILED,
                details=f"Data extraction failed: {str(e)}"
            ))
            component_failures.append("data_extraction")
            # Build minimal extracted data from claim submission
            extracted = ExtractedClaimData(
                documents=[],
                line_items=[],
                total_extracted_amount=claim.claimed_amount,
                hospital_name=claim.hospital_name
            )

        # Step 4: Policy Evaluation
        policy_result = None
        try:
            policy_result, trace = self.policy_evaluator.process(claim, extracted, self.policy)
            trace_steps.append(trace)
        except Exception as e:
            trace_steps.append(TraceStep(
                step_name="policy_evaluation",
                status=TraceStepStatus.FAILED,
                details=f"Policy evaluation failed: {str(e)}"
            ))
            component_failures.append("policy_evaluation")
            # Create a pass-through result with no deductions
            policy_result = PolicyEvaluationResult(
                all_checks_passed=True,
                final_approved_amount=claim.claimed_amount
            )

        # Step 5: Fraud Detection (graceful degradation target)
        fraud_result = None
        try:
            if claim.simulate_component_failure:
                raise RuntimeError("Simulated component failure: Fraud detection service unavailable")
            fraud_result, trace = self.fraud_detector.process(claim, self.policy)
            trace_steps.append(trace)
        except Exception as e:
            trace_steps.append(TraceStep(
                step_name="fraud_detection",
                status=TraceStepStatus.FAILED,
                details=f"Fraud detection failed: {str(e)}. Skipped — manual review recommended."
            ))
            component_failures.append("fraud_detection")

        # Step 6: Decision Aggregation (always runs)
        decision = self.decision_aggregator.process(
            claim=claim,
            policy_result=policy_result,
            fraud_result=fraud_result,
            all_trace_steps=trace_steps,
            component_failures=component_failures
        )

        # Add final aggregation trace step
        trace_steps.append(TraceStep(
            step_name="decision_aggregation",
            status=TraceStepStatus.PASSED,
            details=(
                f"Decision: {decision.decision}. "
                f"Approved: ₹{decision.approved_amount or 0:,.0f}. "
                f"Confidence: {decision.confidence_score:.2f}."
            )
        ))

        # Update decision trace with all steps
        decision.trace = AuditTrace(
            claim_id=claim.claim_id,
            steps=trace_steps,
            component_failures=component_failures
        )

        return decision
