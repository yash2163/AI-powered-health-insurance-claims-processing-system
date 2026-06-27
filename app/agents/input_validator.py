"""
Agent 1: Input Validator

Validates claim submission metadata against policy configuration.
All checks are deterministic — no LLM calls.
"""
from datetime import datetime
from app.models.claim import ClaimSubmission
from app.models.policy import PolicyConfig
from app.models.trace import TraceStep
from app.models.enums import TraceStepStatus
from app.utils.date_utils import is_within_policy_period, is_within_submission_deadline

class InputValidator:
    def process(self, claim: ClaimSubmission, policy: PolicyConfig) -> tuple[bool, list[str], TraceStep]:
        start_time = datetime.utcnow()
        errors = []

        # Check 1: Member exists
        member = policy.members.get(claim.member_id)
        if not member:
            errors.append(f"Member '{claim.member_id}' not found in the policy roster.")

        # Check 2: Policy active
        if not is_within_policy_period(claim.treatment_date, policy.policy_start_date, policy.policy_end_date):
            errors.append(
                f"Treatment date {claim.treatment_date} is outside the policy period "
                f"({policy.policy_start_date} to {policy.policy_end_date})."
            )

        # Check 3: Minimum amount
        min_amount = policy.submission_rules.get("minimum_claim_amount", 500)
        if claim.claimed_amount < min_amount:
            errors.append(
                f"Claimed amount ₹{claim.claimed_amount} is below the minimum claim amount of ₹{min_amount}."
            )

        # Check 4: Submission deadline
        deadline_days = policy.submission_rules.get("deadline_days_from_treatment", 30)
        if not is_within_submission_deadline(claim.treatment_date, claim.submission_date, deadline_days):
            errors.append(
                f"Claim submitted more than {deadline_days} days after treatment date {claim.treatment_date}."
            )

        # Check 5: Valid category
        category_config = policy.opd_categories.get(claim.claim_category.value)
        if not category_config:
            errors.append(f"Claim category '{claim.claim_category.value}' is not recognized.")
        elif not category_config.covered:
            errors.append(f"Category '{claim.claim_category.value}' is not covered under this policy.")

        passed = len(errors) == 0
        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        trace = TraceStep(
            step_name="input_validation",
            status=TraceStepStatus.PASSED if passed else TraceStepStatus.FAILED,
            duration_ms=duration,
            details="; ".join(errors) if errors else (
                f"Member {claim.member_id} valid. Policy active. "
                f"Amount ₹{claim.claimed_amount:,.0f} within limits. "
                f"Category {claim.claim_category.value} covered."
            )
        )

        return passed, errors, trace
