"""
Date arithmetic utilities for policy evaluation.
"""
from datetime import date, timedelta

def parse_date(date_str: str) -> date:
    """Parse YYYY-MM-DD string to date object."""
    if isinstance(date_str, date):
        return date_str
    return date.fromisoformat(str(date_str))

def days_between(d1: date, d2: date) -> int:
    """Return number of days between two dates (d2 - d1)."""
    return (d2 - d1).days

def is_within_policy_period(treatment_date: date, start: str, end: str) -> bool:
    return parse_date(start) <= treatment_date <= parse_date(end)

def is_within_submission_deadline(treatment_date: date, submission_date: date, deadline_days: int) -> bool:
    return (submission_date - treatment_date).days <= deadline_days

def calculate_waiting_period_end(join_date: date, waiting_days: int) -> date:
    return join_date + timedelta(days=waiting_days)

def is_in_waiting_period(treatment_date: date, join_date: date, waiting_days: int) -> tuple[bool, date]:
    """
    Check if treatment_date falls within the waiting period.

    Returns:
        (is_in_waiting: bool, eligible_from: date)
    """
    eligible_from = calculate_waiting_period_end(join_date, waiting_days)
    is_in_waiting = treatment_date < eligible_from
    return is_in_waiting, eligible_from
