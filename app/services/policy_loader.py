"""
Loads and parses policy_terms.json into PolicyConfig.
"""
import json
from app.models.policy import PolicyConfig, CategoryConfig, MemberInfo
from app.models.enums import ClaimCategory

def load_policy(filepath: str) -> PolicyConfig:
    """
    Load policy_terms.json and construct PolicyConfig.
    """
    with open(filepath, "r") as f:
        raw = json.load(f)

    # Build member lookup (keyed by member_id)
    members = {}
    for m in raw["members"]:
        members[m["member_id"]] = MemberInfo(**m)

    # For dependents without join_date, inherit from primary member
    for mid, member in members.items():
        if member.join_date is None and member.primary_member_id:
            primary = members.get(member.primary_member_id)
            if primary:
                member.join_date = primary.join_date

    # Build category configs
    category_map = {
        "consultation": "CONSULTATION",
        "diagnostic": "DIAGNOSTIC",
        "pharmacy": "PHARMACY",
        "dental": "DENTAL",
        "vision": "VISION",
        "alternative_medicine": "ALTERNATIVE_MEDICINE"
    }
    opd_categories = {}
    for json_key, enum_val in category_map.items():
        if json_key in raw["opd_categories"]:
            opd_categories[enum_val] = CategoryConfig(**raw["opd_categories"][json_key])

    return PolicyConfig(
        policy_id=raw["policy_id"],
        policy_name=raw["policy_name"],
        insurer=raw["insurer"],
        company_name=raw["policy_holder"]["company_name"],
        policy_start_date=raw["policy_holder"]["policy_start_date"],
        policy_end_date=raw["policy_holder"]["policy_end_date"],
        sum_insured_per_employee=raw["coverage"]["sum_insured_per_employee"],
        annual_opd_limit=raw["coverage"]["annual_opd_limit"],
        per_claim_limit=raw["coverage"]["per_claim_limit"],
        opd_categories=opd_categories,
        waiting_periods=raw["waiting_periods"],
        exclusions=raw["exclusions"],
        pre_authorization=raw["pre_authorization"],
        network_hospitals=raw["network_hospitals"],
        submission_rules=raw["submission_rules"],
        fraud_thresholds=raw["fraud_thresholds"],
        document_requirements=raw["document_requirements"],
        members=members,
    )

def get_member(policy: PolicyConfig, member_id: str) -> MemberInfo | None:
    return policy.members.get(member_id)

def get_category_config(policy: PolicyConfig, category: ClaimCategory) -> CategoryConfig | None:
    return policy.opd_categories.get(category.value)

def get_document_requirements(policy: PolicyConfig, category: ClaimCategory) -> dict:
    return policy.document_requirements.get(category.value, {"required": [], "optional": []})

def is_network_hospital(policy: PolicyConfig, hospital_name: str) -> bool:
    if not hospital_name:
        return False
    hospital_lower = hospital_name.lower()
    for network in policy.network_hospitals:
        if network.lower() in hospital_lower or hospital_lower in network.lower():
            return True
    return False
