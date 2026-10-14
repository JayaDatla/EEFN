"""
Does the A-F "evidence health" grade actually separate planets from false positives?

The grade is a catalog-consistency summary (agreement of TOI and Gaia values, RUWE, plausible derived
radius, completeness). It is NOT a probability that a planet is real, and a letter grade invites being
read as one. This module measures, on every labelled candidate in the database, how well the 0-100
score ranks confirmed planets above false positives, and what share of each grade is labelled FP --
computed live, so the numbers shown to users cannot go stale.
"""
from typing import Any, Dict, Iterable, List, Optional

from app.science.prospective import wilson_interval


def _auc(scores: List[float], labels: List[int]) -> Optional[float]:
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def validate_health(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """rows: {"disposition", "health_score", "health_grade"}. Planets = CP/KP, false positives = FP/FA."""
    labelled = [r for r in rows if r.get("disposition") in ("CP", "KP", "FP", "FA") and r.get("health_score") is not None]
    labels = [1 if r["disposition"] in ("CP", "KP") else 0 for r in labelled]
    n_fp = labels.count(0)
    by_grade = {}
    for g in "ABCDF":
        in_g = [r for r in labelled if r.get("health_grade") == g]
        fp = sum(1 for r in in_g if r["disposition"] in ("FP", "FA"))
        by_grade[g] = {"n": len(in_g), "false_positive_share": (fp / len(in_g)) if in_g else None,
                       "ci95": wilson_interval(fp, len(in_g)) if in_g else None}
    return {
        "n_labelled": len(labelled), "base_rate_false_positive": (n_fp / len(labelled)) if labelled else None,
        "auc_planet_vs_false_positive": _auc([r["health_score"] for r in labelled], labels),
        "by_grade": by_grade,
        "interpretation": ("A catalog-consistency grade, not a planet probability. Read 'A' as 'no catalog red flags', "
                           "not as 'likely a planet': compare each grade's false-positive share with the base rate."),
    }
