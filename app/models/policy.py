from pydantic import BaseModel
from typing import Optional

class CategoryConfig(BaseModel):
    """Configuration for a single OPD category from policy_terms.json."""
    sub_limit: float
    copay_percent: float
    network_discount_percent: float = 0.0
    requires_prescription: bool = False
    requires_pre_auth: bool = False
    requires_dental_report: bool = False
    requires_registered_practitioner: bool = False
    pre_auth_threshold: Optional[float] = None
    high_value_tests_requiring_pre_auth: list[str] = []
    covered: bool = True
    covered_procedures: list[str] = []
    excluded_procedures: list[str] = []
    covered_items: list[str] = []
    excluded_items: list[str] = []
    covered_systems: list[str] = []
    max_sessions_per_year: Optional[int] = None
    branded_drug_copay_percent: float = 0.0
    generic_mandatory: bool = False

class MemberInfo(BaseModel):
    """A member from the policy member roster."""
    member_id: str
    name: str
    date_of_birth: str
    gender: str
    relationship: str
    join_date: Optional[str] = None            # Present for employees
    primary_member_id: Optional[str] = None    # Present for dependents
    dependents: list[str] = []

class PolicyConfig(BaseModel):
    """Complete policy configuration loaded from policy_terms.json."""
    policy_id: str
    policy_name: str
    insurer: str
    company_name: str
    policy_start_date: str
    policy_end_date: str
    sum_insured_per_employee: float
    annual_opd_limit: float
    per_claim_limit: float
    opd_categories: dict[str, CategoryConfig]
    waiting_periods: dict  # Raw dict from JSON — initial + specific conditions
    exclusions: dict       # Raw dict — conditions, dental, vision
    pre_authorization: dict
    network_hospitals: list[str]
    submission_rules: dict
    fraud_thresholds: dict
    document_requirements: dict[str, dict[str, list[str]]]  # category -> required/optional -> doc types
    members: dict[str, MemberInfo]  # Keyed by member_id for O(1) lookup
