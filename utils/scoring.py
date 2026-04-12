"""
Scoring utility functions for startup suitability and hot area ranking.
"""
from typing import Dict, List, Tuple


def normalize_score(value: float, min_val: float, max_val: float, invert: bool = False) -> float:
    """
    Normalize a value to 0-100 scale.

    Args:
        value: Raw value
        min_val: Minimum expected value (maps to 0 or 100 if inverted)
        max_val: Maximum expected value (maps to 100 or 0 if inverted)
        invert: If True, higher raw value = lower score (e.g., competition density)
    """
    if max_val == min_val:
        return 50.0
    clamped = max(min_val, min(value, max_val))
    normalized = (clamped - min_val) / (max_val - min_val) * 100
    return round(100 - normalized if invert else normalized, 1)


def weighted_composite(scores: Dict[str, float], weights: Dict[str, float]) -> float:
    """
    Compute weighted average score, redistributing weight for missing factors.

    Args:
        scores: {"factor_name": score_0_to_100, ...} — None values are skipped
        weights: {"factor_name": weight_0_to_1, ...}

    Returns:
        Weighted average score (0-100)
    """
    available_total_weight = 0
    weighted_sum = 0

    for factor, weight in weights.items():
        score = scores.get(factor)
        if score is not None:
            available_total_weight += weight
            weighted_sum += score * weight

    if available_total_weight == 0:
        return 50.0  # No data = neutral

    # Redistribute: scale up to compensate for missing factors
    return round(weighted_sum / available_total_weight, 1)


def score_to_grade(score: float, thresholds: List[Tuple[float, str]]) -> str:
    """
    Convert score to grade based on thresholds.

    Args:
        score: Numeric score
        thresholds: [(max_value, grade_label), ...] sorted ascending.
                    Last entry is the default.

    Example:
        score_to_grade(75, [(20, "매우부적합"), (40, "부적합"), (60, "보통"), (80, "적합"), (100, "매우적합")])
        → "적합"
    """
    for threshold, grade in thresholds:
        if score <= threshold:
            return grade
    return thresholds[-1][1] if thresholds else "N/A"


# Pre-defined grade scales
STARTUP_GRADES = [
    (20, "매우부적합"),
    (40, "부적합"),
    (60, "보통"),
    (80, "적합"),
    (100, "매우적합"),
]

CLOSURE_GRADES = [
    (10, "안정"),
    (20, "보통"),
    (30, "주의"),
    (100, "위험"),
]
