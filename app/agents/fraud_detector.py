from datetime import datetime
from typing import Tuple

from app.models.claim import ClaimSubmission
from app.models.policy import PolicyConfig
from app.models.decision import FraudCheckResult, FraudSignal
from app.models.trace import TraceStep
from app.models.enums import TraceStepStatus

class FraudDetector:
    def process(self, claim: ClaimSubmission, policy: PolicyConfig) -> Tuple[FraudCheckResult, TraceStep]:
        start_time = datetime.utcnow()
        signals = []
        thresholds = policy.fraud_thresholds
        history = claim.claims_history or []

        # Check 1: Same-day claims
        treatment_date_str = str(claim.treatment_date)
        same_day_count = sum(1 for h in history if h.date == treatment_date_str)
        # Total including current claim
        total_same_day = same_day_count + 1
        same_day_limit = thresholds.get("same_day_claims_limit", 2)
        if total_same_day > same_day_limit:
            signals.append(FraudSignal(
                signal_type="SAME_DAY_CLAIMS",
                current_value=float(total_same_day),
                threshold=float(same_day_limit),
                description=(
                    f"{total_same_day} claims on {treatment_date_str} "
                    f"(limit: {same_day_limit}). Pattern suggests possible fraud."
                )
            ))

        # Check 2: Monthly claims
        treatment_month = claim.treatment_date.strftime("%Y-%m")
        monthly_count = sum(1 for h in history if h.date.startswith(treatment_month))
        monthly_total = monthly_count + 1
        monthly_limit = thresholds.get("monthly_claims_limit", 6)
        if monthly_total > monthly_limit:
            signals.append(FraudSignal(
                signal_type="MONTHLY_CLAIMS_EXCEEDED",
                current_value=float(monthly_total),
                threshold=float(monthly_limit),
                description=f"{monthly_total} claims in {treatment_month} (limit: {monthly_limit})."
            ))

        # Check 3: High-value claim
        high_value_threshold = thresholds.get("high_value_claim_threshold", 25000)
        if claim.claimed_amount > high_value_threshold:
            signals.append(FraudSignal(
                signal_type="HIGH_VALUE_CLAIM",
                current_value=claim.claimed_amount,
                threshold=float(high_value_threshold),
                description=f"Claim ₹{claim.claimed_amount:,.0f} exceeds high-value threshold ₹{high_value_threshold:,.0f}."
            ))

        requires_review = len(signals) > 0
        details = "; ".join(s.description for s in signals) if signals else "No fraud signals detected."

        result = FraudCheckResult(
            signals=signals,
            requires_manual_review=requires_review,
            details=details
        )

        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        trace = TraceStep(
            step_name="fraud_detection",
            status=TraceStepStatus.PASSED,
            duration_ms=duration,
            details=(
                f"Fraud checks completed. "
                f"Same-day claims count: {total_same_day} (limit: {same_day_limit}). "
                f"Monthly claims count: {monthly_total} (limit: {monthly_limit}). "
                f"High-value threshold check: ₹{claim.claimed_amount:,.2f} vs limit ₹{high_value_threshold:,.2f}. "
                + (f"FLAGGED for manual review: {details}" if requires_review else "No flags raised. All frequency checks passed.")
            )
        )

        return result, trace
