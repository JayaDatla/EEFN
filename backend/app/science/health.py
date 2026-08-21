"""
Single source of truth for EEFN's evidence-consistency health score.

Before this module existed, `backend/app/pipeline/ingest.py` and
`backend/services/alert_engine.py` each computed a health score inline, with different
caps and missing terms -- the same candidate could grade differently depending which
code path last touched it (UPGRADE_PLAN.md A.3). Every caller in the codebase must use
`compute_health_score` (ORM-object callers) or `compute_health_score_from_values`
(callers building the score before the ORM rows exist, e.g. during ingestion) -- never
reimplement the formula.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# Bump whenever the term weights/caps below change, so a stored `health_score_version`
# on ExoplanetCandidate tells you whether a historical score is comparable to a fresh one.
HEALTH_SCORE_VERSION = "1.1.0"


@dataclass
class HealthResult:
    score: float
    grade: str
    factors: Dict[str, float]
    version: str = HEALTH_SCORE_VERSION


def _grade_for(score: float) -> str:
    if score >= 90.0:
        return "A"
    if score >= 80.0:
        return "B"
    if score >= 70.0:
        return "C"
    if score >= 60.0:
        return "D"
    return "F"


def compute_health_score_from_values(
    teff_disagreement: Optional[float],
    rad_disagreement: Optional[float],
    dist_disagreement: Optional[float],
    ruwe: Optional[float],
    is_unphysical_rp: bool,
    completeness_score: Optional[float],
    query_failed: bool,
) -> HealthResult:
    """
    Core formula, usable before any ORM row exists (e.g. mid-ingestion, while a
    candidate's row is still being assembled). Reconciles the two prior
    implementations: takes `alert_engine.py`'s fuller term set (it already had the
    distance and completeness terms `ingest.py` lacked) as the base, and folds in
    `ingest.py`'s `query_failed` penalty, which `alert_engine.py` lacked.
    """
    score = 100.0
    factors = {
        "agreement": 100.0,
        "completeness": 100.0,
        "provenance_quality": 100.0,
        "measurement_consistency": 100.0,
    }

    teff_deduction = min(20.0, (teff_disagreement or 0.0) / 20.0)
    score -= teff_deduction
    factors["agreement"] -= teff_deduction * 2

    rad_deduction = min(20.0, (rad_disagreement or 0.0) / 0.05)
    score -= rad_deduction
    factors["agreement"] -= rad_deduction * 2

    dist_deduction = min(10.0, (dist_disagreement or 0.0) / 10.0)
    score -= dist_deduction
    factors["agreement"] -= dist_deduction

    if ruwe and ruwe > 1.4:
        score -= 15.0
        factors["measurement_consistency"] -= 30.0

    if is_unphysical_rp:
        score -= 25.0
        factors["measurement_consistency"] -= 50.0

    comp_score = completeness_score if completeness_score is not None else 1.0
    comp_deduction = (1.0 - comp_score) * 20.0
    score -= comp_deduction
    factors["completeness"] -= comp_deduction * 5

    if query_failed:
        score -= 15.0
        factors["provenance_quality"] -= 30.0

    score = max(0.0, min(100.0, score))

    return HealthResult(
        score=round(score, 1),
        grade=_grade_for(score),
        factors={k: round(v, 1) for k, v in factors.items()},
    )


def compute_health_score(metrics: Optional[Any], candidate: Optional[Any]) -> HealthResult:
    """
    Convenience wrapper for callers holding real `AgreementMetrics`/`ExoplanetCandidate`
    ORM rows (e.g. `AlertEngine.calculate_health_score`).
    """
    return compute_health_score_from_values(
        teff_disagreement=metrics.teff_disagreement if metrics else None,
        rad_disagreement=metrics.rad_disagreement if metrics else None,
        dist_disagreement=metrics.dist_disagreement if metrics else None,
        ruwe=metrics.ruwe if metrics else None,
        is_unphysical_rp=bool(metrics.is_unphysical_rp) if metrics else False,
        completeness_score=metrics.completeness_score if metrics else None,
        query_failed=bool(candidate.query_failed) if candidate else False,
    )
