"""
Fuzzy text matching utilities for patient name comparison.
"""
from Levenshtein import ratio as levenshtein_ratio

def normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, strip titles, collapse whitespace."""
    if not name:
        return ""
    name = name.lower().strip()
    # Remove common Indian honorifics
    for prefix in ["mr.", "mrs.", "ms.", "dr.", "shri", "smt.", "master"]:
        if name.startswith(prefix):
            name = name[len(prefix):].strip()
    # Collapse multiple spaces
    return " ".join(name.split())

def names_match(name1: str, name2: str, threshold: float = 0.75) -> tuple[bool, float]:
    """
    Compare two patient names using normalized Levenshtein ratio.

    Returns:
        (is_match: bool, similarity_score: float)
    """
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)
    if not n1 or not n2:
        return False, 0.0
    score = levenshtein_ratio(n1, n2)
    return score >= threshold, score
