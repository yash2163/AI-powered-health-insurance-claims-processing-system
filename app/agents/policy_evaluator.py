import json
from datetime import datetime
from typing import Tuple, List, Dict, Any

from app.models.claim import ClaimSubmission
from app.models.policy import PolicyConfig, CategoryConfig, MemberInfo
from app.models.document import ExtractedClaimData, LineItem
from app.models.decision import (
    PolicyEvaluationResult, PolicyCheck, Deduction, LineItemDecision
)
from app.models.enums import RejectionReason, RuleSource, TraceStepStatus
from app.models.trace import TraceStep
from app.utils.date_utils import parse_date, is_in_waiting_period
from app.services.policy_loader import get_category_config, get_member, is_network_hospital

class PolicyEvaluator:
    def __init__(self, gemini_client=None):
        self.gemini_client = gemini_client

    def process(
        self,
        claim: ClaimSubmission,
        extracted: ExtractedClaimData,
        policy: PolicyConfig
    ) -> Tuple[PolicyEvaluationResult, TraceStep]:

        start_time = datetime.utcnow()
        checks = []
        rejection_reasons = []
        rejection_details = []

        category_config = get_category_config(policy, claim.claim_category)
        member = get_member(policy, claim.member_id)

        if not member:
            result = PolicyEvaluationResult(
                checks=[],
                all_checks_passed=False,
                rejection_reasons=[RejectionReason.MEMBER_NOT_FOUND],
                rejection_details=[f"Member '{claim.member_id}' not found in roster."],
                final_approved_amount=0.0
            )
            duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            trace = self._build_trace(result, duration)
            return result, trace

        # ============================================================
        # STEP A: LLM Classifier (semantic matching)
        # ============================================================
        llm_classification = self._run_llm_classifier(
            extracted, policy, claim.claim_category, category_config
        )

        # ============================================================
        # STEP B: Deterministic Engine
        # ============================================================

        # --- Phase 1: Hard Rejection Gates ---

        # 1.1 Waiting Period
        waiting_check = self._check_waiting_period(
            claim, member, extracted, policy, llm_classification
        )
        checks.append(waiting_check)
        if not waiting_check.passed:
            rejection_reasons.append(RejectionReason.WAITING_PERIOD)
            rejection_details.append(waiting_check.details)

        # 1.2 Pre-Authorization
        preauth_check = self._check_pre_authorization(
            claim, extracted, policy, category_config, llm_classification
        )
        checks.append(preauth_check)
        if not preauth_check.passed:
            rejection_reasons.append(RejectionReason.PRE_AUTH_MISSING)
            rejection_details.append(preauth_check.details)

        # 1.3 Full Exclusion Check
        exclusion_check = self._check_full_exclusion(
            extracted, policy, llm_classification
        )
        checks.append(exclusion_check)
        if not exclusion_check.passed:
            rejection_reasons.append(RejectionReason.EXCLUDED_CONDITION)
            rejection_details.append(exclusion_check.details)

        # If any Phase 1 gate failed → short-circuit to REJECTED
        if rejection_reasons:
            result = PolicyEvaluationResult(
                checks=checks,
                all_checks_passed=False,
                rejection_reasons=rejection_reasons,
                rejection_details=rejection_details,
                final_approved_amount=0.0
            )
            duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            trace = self._build_trace(result, duration)
            return result, trace

        # --- Phase 2: Line-Item Filtering ---
        line_item_decisions = self._filter_line_items(
            extracted, policy, claim.claim_category, category_config, llm_classification
        )
        approved_items = [d for d in line_item_decisions if d.approved]
        excluded_items = [d for d in line_item_decisions if not d.approved]
        post_filter_amount = sum(d.amount for d in approved_items)
        is_partial = len(excluded_items) > 0 and len(approved_items) > 0

        line_items_check = PolicyCheck(
            check_name="line_item_filtering",
            passed=len(approved_items) > 0,
            details=(
                f"{len(approved_items)} items approved (₹{post_filter_amount:,.0f}), "
                f"{len(excluded_items)} items excluded."
            ),
            source=RuleSource.LLM if excluded_items else RuleSource.DETERMINISTIC
        )
        checks.append(line_items_check)

        # If all items were excluded after line-item filtering, we reject the whole claim
        if len(approved_items) == 0:
            result = PolicyEvaluationResult(
                checks=checks,
                all_checks_passed=False,
                rejection_reasons=[RejectionReason.EXCLUDED_CONDITION],
                rejection_details=["All line items in the claim are excluded under the policy terms."],
                line_item_decisions=line_item_decisions,
                final_approved_amount=0.0
            )
            duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            trace = self._build_trace(result, duration)
            return result, trace

        # --- Phase 3: Per-Claim Limit Check ---
        effective_cap = max(policy.per_claim_limit, category_config.sub_limit if category_config else 0.0)
        per_claim_passed = post_filter_amount <= effective_cap
        per_claim_check = PolicyCheck(
            check_name="per_claim_limit",
            passed=per_claim_passed,
            details=(
                f"Post-filter amount ₹{post_filter_amount:,.0f} vs effective cap "
                f"₹{effective_cap:,.0f} (max of per_claim_limit ₹{policy.per_claim_limit:,.0f} "
                f"and category sub_limit ₹{category_config.sub_limit if category_config else 0.0:,.0f})."
            ),
            source=RuleSource.DETERMINISTIC
        )
        checks.append(per_claim_check)
        if not per_claim_passed:
            rejection_reasons.append(RejectionReason.PER_CLAIM_EXCEEDED)
            rejection_details.append(
                f"Claimed amount ₹{post_filter_amount:,.0f} exceeds the per-claim limit of "
                f"₹{effective_cap:,.0f}. The maximum allowed per claim for "
                f"{claim.claim_category.value.lower()} is ₹{effective_cap:,.0f}."
            )
            result = PolicyEvaluationResult(
                checks=checks,
                all_checks_passed=False,
                rejection_reasons=rejection_reasons,
                rejection_details=rejection_details,
                line_item_decisions=line_item_decisions,
                pre_deduction_amount=post_filter_amount,
                final_approved_amount=0.0
            )
            duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            trace = self._build_trace(result, duration)
            return result, trace

        # --- Phase 4: Amount Calculation ---
        deductions = []
        amount = post_filter_amount

        # 4.1 Network discount
        hospital = extracted.hospital_name or claim.hospital_name or ""
        is_network = is_network_hospital(policy, hospital)
        if is_network and category_config and category_config.network_discount_percent > 0:
            discount_pct = category_config.network_discount_percent
            discount_amt = amount * (discount_pct / 100)
            amount -= discount_amt
            deductions.append(Deduction(
                deduction_type="NETWORK_DISCOUNT",
                amount=discount_amt,
                description=(
                    f"Network hospital discount ({discount_pct}%) on ₹{post_filter_amount:,.0f} "
                    f"= ₹{discount_amt:,.0f} deducted. After discount: ₹{amount:,.0f}."
                )
            ))

        # 4.2 Copay
        if category_config:
            copay_pct = category_config.copay_percent
            if copay_pct > 0:
                copay_amt = amount * (copay_pct / 100)
                amount -= copay_amt
                deductions.append(Deduction(
                    deduction_type="COPAY",
                    amount=copay_amt,
                    description=(
                        f"Co-pay ({copay_pct}%) on ₹{amount + copay_amt:,.0f} "
                        f"= ₹{copay_amt:,.0f} deducted. After co-pay: ₹{amount:,.0f}."
                    )
                ))

        # 4.3 Annual OPD limit check
        if claim.ytd_claims_amount is not None:
            remaining_budget = policy.annual_opd_limit - claim.ytd_claims_amount
            if amount > remaining_budget:
                cap_amount = amount - remaining_budget
                amount = remaining_budget
                deductions.append(Deduction(
                    deduction_type="ANNUAL_LIMIT_CAP",
                    amount=cap_amount,
                    description=(
                        f"Annual OPD limit ₹{policy.annual_opd_limit:,.0f}, "
                        f"YTD used ₹{claim.ytd_claims_amount:,.0f}, "
                        f"remaining ₹{remaining_budget:,.0f}. Capped to ₹{amount:,.0f}."
                    )
                ))

        final_approved = round(amount, 2)

        amount_check = PolicyCheck(
            check_name="amount_calculation",
            passed=True,
            details=(
                f"Base: ₹{post_filter_amount:,.0f}. "
                + " → ".join([d.description for d in deductions])
                + f" Final: ₹{final_approved:,.0f}."
                if deductions else
                f"No deductions applied. Approved: ₹{final_approved:,.0f}."
            ),
            source=RuleSource.DETERMINISTIC
        )
        checks.append(amount_check)

        result = PolicyEvaluationResult(
            checks=checks,
            all_checks_passed=True,
            rejection_reasons=[],
            rejection_details=[],
            line_item_decisions=line_item_decisions,
            approved_line_items=[{"description": d.description, "amount": d.amount} for d in approved_items],
            excluded_line_items=[{"description": d.description, "amount": d.amount, "reason": d.reason} for d in excluded_items],
            pre_deduction_amount=post_filter_amount,
            deductions=deductions,
            final_approved_amount=final_approved,
            is_partial=is_partial
        )

        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        trace = self._build_trace(result, duration)
        return result, trace

    def _run_llm_classifier(self, extracted: ExtractedClaimData, policy: PolicyConfig, category: Any, category_config: Any) -> Dict[str, Any]:
        """
        Call Gemini text-only for semantic classification.
        """
        if not self.gemini_client:
            return self._fallback_classification(extracted, policy, category, category_config)

        try:
            exclusions_json = json.dumps(policy.exclusions)
            covered_procedures_json = json.dumps(category_config.covered_procedures if category_config else [])
            excluded_procedures_json = json.dumps(category_config.excluded_procedures if category_config else [])
            waiting_conditions_json = json.dumps(policy.waiting_periods.get("specific_conditions", {}))
            preauth_requirements_json = json.dumps(policy.pre_authorization)
            line_items_json = json.dumps([{"description": item.description, "amount": item.amount} for item in extracted.line_items])

            result = self.gemini_client.classify_policy_terms(
                diagnosis=extracted.primary_diagnosis or "",
                treatment=extracted.primary_treatment or "",
                line_items_json=line_items_json,
                category=category.value,
                exclusions_json=exclusions_json,
                covered_procedures_json=covered_procedures_json,
                excluded_procedures_json=excluded_procedures_json,
                waiting_conditions_json=waiting_conditions_json,
                preauth_requirements_json=preauth_requirements_json
            )
            return result
        except Exception:
            return self._fallback_classification(extracted, policy, category, category_config)

    def _fallback_classification(self, extracted: ExtractedClaimData, policy: PolicyConfig, category: Any, category_config: Any) -> Dict[str, Any]:
        """
        Deterministic fallback when no LLM is available.
        Uses keyword matching for exclusions and condition mapping.
        """
        import re
        diagnosis = (extracted.primary_diagnosis or "").lower()
        treatment = (extracted.primary_treatment or "").lower()
        line_items = extracted.line_items

        # --- 1. Waiting Period Condition Mapping ---
        CONDITION_KEYWORDS = {
            "diabetes": ["diabetes", "t2dm", "type 2 diabetes", "type 1 diabetes", "diabetic"],
            "hypertension": ["hypertension", "htn", "high blood pressure"],
            "thyroid_disorders": ["thyroid", "hypothyroid", "hyperthyroid"],
            "joint_replacement": ["joint replacement", "knee replacement", "hip replacement"],
            "maternity": ["maternity", "pregnancy", "prenatal"],
            "mental_health": ["depression", "anxiety", "mental health", "psychiatric"],
            "obesity_treatment": ["obesity", "bariatric", "weight loss", "bmi"],
            "hernia": ["hernia"],
            "cataract": ["cataract"],
        }
        matched_condition = None
        condition_confidence = 0.0
        for condition_key, keywords in CONDITION_KEYWORDS.items():
            if any(re.search(rf"\b{re.escape(kw)}\b", diagnosis) for kw in keywords):
                matched_condition = condition_key
                condition_confidence = 0.95
                break

        # --- 2. Exclusion Matching ---
        EXCLUSION_KEYWORDS = {
            "Obesity and weight loss programs": ["obesity", "weight loss", "diet plan", "diet program",
                                                  "nutrition program", "bmi", "bariatric"],
            "Bariatric surgery": ["bariatric"],
            "Cosmetic or aesthetic procedures": ["cosmetic", "aesthetic", "whitening", "bleaching", "veneers"],
            "Self-inflicted injuries": ["self-inflicted", "self harm"],
            "Substance abuse treatment": ["substance abuse", "alcohol", "drug abuse"],
            "Experimental treatments": ["experimental"],
            "Infertility and assisted reproduction": ["infertility", "ivf", "assisted reproduction"],
            "Health supplements and tonics": ["supplement", "tonic"],
        }
        exclusion_matches = []
        combined_text = f"{diagnosis} {treatment}".lower()
        for exclusion_name, keywords in EXCLUSION_KEYWORDS.items():
            if any(re.search(rf"\b{re.escape(kw)}\b", combined_text) for kw in keywords):
                exclusion_matches.append({
                    "item": combined_text.strip(),
                    "matched_exclusion": exclusion_name,
                    "confidence": 0.95,
                    "reasoning": "Keyword match found in diagnosis/treatment text"
                })

        # --- 3. Line Item Classification ---
        line_item_classifications = []
        for item in line_items:
            desc_lower = item.description.lower()
            is_covered = True
            matched_rule = None

            # Check against category-specific excluded procedures
            if category_config and category_config.excluded_procedures:
                for excl in category_config.excluded_procedures:
                    if re.search(rf"\b{re.escape(excl.lower())}\b", desc_lower) or re.search(rf"\b{re.escape(desc_lower)}\b", excl.lower()):
                        is_covered = False
                        matched_rule = f"Excluded procedure: {excl}"
                        break

            # Check against general exclusion keywords
            if is_covered:
                for excl_name, keywords in EXCLUSION_KEYWORDS.items():
                    if any(re.search(rf"\b{re.escape(kw)}\b", desc_lower) for kw in keywords):
                        is_covered = False
                        matched_rule = f"Matches exclusion: {excl_name}"
                        break

            # Check against category-specific covered procedures (dental/vision)
            if is_covered and category_config and category_config.covered_procedures:
                found_in_covered = False
                for cov in category_config.covered_procedures:
                    if re.search(rf"\b{re.escape(cov.lower())}\b", desc_lower) or re.search(rf"\b{re.escape(desc_lower)}\b", cov.lower()):
                        found_in_covered = True
                        matched_rule = f"Covered procedure: {cov}"
                        break
                # For dental/vision, if not found in covered list, it's still covered
                # unless it was explicitly in excluded list (already checked above)

            line_item_classifications.append({
                "description": item.description,
                "amount": item.amount,
                "is_covered": is_covered,
                "matched_rule": matched_rule,
                "confidence": 0.95 if matched_rule else 0.80,
                "reasoning": matched_rule or "No specific rule matched; treated as covered"
            })

        # --- 4. Pre-Authorization Detection ---
        requires_preauth = False
        preauth_reason = None
        preauth_keywords = ["mri", "ct scan", "pet scan", "magnetic resonance"]
        all_text = f"{diagnosis} {treatment} {' '.join(i.description for i in line_items)}".lower()
        for kw in preauth_keywords:
            if re.search(rf"\b{re.escape(kw)}\b", all_text):
                requires_preauth = True
                preauth_reason = f"Treatment involves {kw.upper()} which requires pre-authorization"
                break

        return {
            "exclusion_matches": exclusion_matches,
            "waiting_period_condition": {
                "matched_condition": matched_condition,
                "confidence": condition_confidence,
                "reasoning": f"Keyword match for '{matched_condition}'" if matched_condition else "No specific condition matched"
            },
            "line_item_classifications": line_item_classifications,
            "requires_pre_authorization": {
                "required": requires_preauth,
                "reason": preauth_reason,
                "confidence": 0.95 if requires_preauth else 0.90
            }
        }

    def _check_waiting_period(self, claim: ClaimSubmission, member: MemberInfo, extracted: ExtractedClaimData, policy: PolicyConfig, llm_result: Dict[str, Any]) -> PolicyCheck:
        """
        Check initial waiting period (30 days) and condition-specific waiting periods.
        """
        join_date = parse_date(member.join_date)
        treatment = claim.treatment_date
        initial_days = policy.waiting_periods.get("initial_waiting_period_days", 30)

        # Check 1: Initial waiting period
        in_initial, initial_eligible = is_in_waiting_period(treatment, join_date, initial_days)
        if in_initial:
            return PolicyCheck(
                check_name="waiting_period_initial",
                passed=False,
                details=(
                    f"Treatment date {treatment} is within the {initial_days}-day initial "
                    f"waiting period. Member joined {join_date}. "
                    f"Eligible from: {initial_eligible.isoformat()}."
                ),
                source=RuleSource.DETERMINISTIC
            )

        # Check 2: Condition-specific waiting period
        wp_result = llm_result.get("waiting_period_condition", {})
        matched_condition = wp_result.get("matched_condition")
        if matched_condition:
            specific_conditions = policy.waiting_periods.get("specific_conditions", {})
            condition_days = specific_conditions.get(matched_condition)
            if condition_days:
                in_wp, eligible_from = is_in_waiting_period(treatment, join_date, condition_days)
                if in_wp:
                    return PolicyCheck(
                        check_name="waiting_period_condition",
                        passed=False,
                        details=(
                            f"Diagnosis maps to '{matched_condition}' which has a "
                            f"{condition_days}-day waiting period. Member joined {join_date}. "
                            f"Treatment date {treatment} is before eligibility date "
                            f"{eligible_from.isoformat()}. The member will be eligible for "
                            f"{matched_condition}-related claims from {eligible_from.isoformat()}."
                        ),
                        source=RuleSource.LLM,
                        data={"condition": matched_condition, "days": condition_days,
                              "eligible_from": eligible_from.isoformat()}
                    )

        return PolicyCheck(
            check_name="waiting_period",
            passed=True,
            details="No applicable waiting period or waiting period has elapsed.",
            source=RuleSource.DETERMINISTIC
        )

    def _check_pre_authorization(self, claim: ClaimSubmission, extracted: ExtractedClaimData, policy: PolicyConfig, category_config: CategoryConfig, llm_result: Dict[str, Any]) -> PolicyCheck:
        """
        Check if pre-authorization is required and was obtained.
        """
        preauth_result = llm_result.get("requires_pre_authorization", {})
        requires = preauth_result.get("required", False)

        # Also check deterministically for diagnostic category
        if category_config and category_config.high_value_tests_requiring_pre_auth:
            threshold = category_config.pre_auth_threshold or 10000
            if claim.claimed_amount > threshold:
                # Check if any line item or test matches high-value tests
                all_text = " ".join(
                    item.description for item in extracted.line_items
                ).lower() if extracted.line_items else ""
                for test in category_config.high_value_tests_requiring_pre_auth:
                    if test.lower() in all_text:
                        requires = True
                        break

        if not requires:
            return PolicyCheck(
                check_name="pre_authorization",
                passed=True,
                details="Pre-authorization not required for this treatment.",
                source=RuleSource.DETERMINISTIC
            )

        # Pre-auth is required — check if obtained
        if claim.pre_auth_approved:
            return PolicyCheck(
                check_name="pre_authorization",
                passed=True,
                details="Pre-authorization was required and has been obtained.",
                source=RuleSource.DETERMINISTIC
            )

        return PolicyCheck(
            check_name="pre_authorization",
            passed=False,
            details=(
                f"Pre-authorization is required for this treatment "
                f"(amount ₹{claim.claimed_amount:,.0f} exceeds threshold). "
                f"No pre-authorization was obtained. Please obtain pre-authorization "
                f"from your insurer before undergoing the treatment and resubmit the claim."
            ),
            source=RuleSource.DETERMINISTIC
        )

    def _check_full_exclusion(self, extracted: ExtractedClaimData, policy: PolicyConfig, llm_result: Dict[str, Any]) -> PolicyCheck:
        """
        Check if the ENTIRE claim is excluded.
        """
        exclusion_matches = llm_result.get("exclusion_matches", [])
        line_classifications = llm_result.get("line_item_classifications", [])

        # Check if diagnosis/treatment level exclusion exists
        has_diagnosis_exclusion = len(exclusion_matches) > 0 and any(
            m.get("confidence", 0) >= 0.7 for m in exclusion_matches
        )

        # Check if ALL line items are excluded
        all_items_excluded = False
        if line_classifications:
            all_items_excluded = all(
                not item.get("is_covered", True) for item in line_classifications
            )
        elif has_diagnosis_exclusion:
            # No line items to check, but diagnosis is excluded
            all_items_excluded = True

        if has_diagnosis_exclusion and all_items_excluded:
            matched_names = [m["matched_exclusion"] for m in exclusion_matches]
            return PolicyCheck(
                check_name="exclusion_check",
                passed=False,
                details=(
                    f"Treatment is excluded under policy. "
                    f"Matched exclusions: {', '.join(matched_names)}. "
                    f"Diagnosis '{extracted.primary_diagnosis}' and all billed items "
                    f"fall under excluded conditions."
                ),
                source=RuleSource.LLM,
                data={"exclusion_matches": exclusion_matches}
            )

        return PolicyCheck(
            check_name="exclusion_check",
            passed=True,
            details="No full-claim exclusions apply." + (
                f" Note: {len(exclusion_matches)} partial exclusion signals detected."
                if exclusion_matches and not all_items_excluded else ""
            ),
            source=RuleSource.LLM if exclusion_matches else RuleSource.DETERMINISTIC
        )

    def _filter_line_items(self, extracted: ExtractedClaimData, policy: PolicyConfig, category: Any, category_config: CategoryConfig, llm_result: Dict[str, Any]) -> List[LineItemDecision]:
        """
        Classify each line item as covered or excluded.
        """
        line_classifications = llm_result.get("line_item_classifications", [])
        decisions = []

        if line_classifications:
            for lc in line_classifications:
                decisions.append(LineItemDecision(
                    description=lc["description"],
                    amount=lc["amount"],
                    approved=lc["is_covered"],
                    reason=lc.get("matched_rule") if not lc["is_covered"] else None
                ))
        elif extracted.line_items:
            for item in extracted.line_items:
                decisions.append(LineItemDecision(
                    description=item.description,
                    amount=item.amount,
                    approved=True,
                    reason=None
                ))
        else:
            decisions.append(LineItemDecision(
                description="Total claim amount",
                amount=extracted.total_extracted_amount or 0.0,
                approved=True,
                reason=None
            ))

        return decisions

    def _build_trace(self, result: PolicyEvaluationResult, duration_ms: int) -> TraceStep:
        """Build trace step summarizing all checks and calculations."""
        if result.all_checks_passed:
            details = (
                f"All policy checks passed. "
                f"Pre-deduction: ₹{result.pre_deduction_amount:,.0f}. "
                f"Deductions: {len(result.deductions)}. "
                f"Final approved: ₹{result.final_approved_amount:,.0f}."
            )
            if result.is_partial:
                details += (
                    f" PARTIAL: {len(result.excluded_line_items)} items excluded."
                )
        else:
            details = (
                f"Policy check failed. Reasons: "
                + "; ".join(result.rejection_details)
            )

        return TraceStep(
            step_name="policy_evaluation",
            status=TraceStepStatus.PASSED if result.all_checks_passed else TraceStepStatus.FAILED,
            duration_ms=duration_ms,
            details=details
        )
