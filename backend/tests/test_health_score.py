import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.science.health import compute_health_score_from_values, HEALTH_SCORE_VERSION


def test_perfect_candidate_grades_a():
    result = compute_health_score_from_values(
        teff_disagreement=0.0, rad_disagreement=0.0, dist_disagreement=0.0,
        ruwe=1.0, is_unphysical_rp=False, completeness_score=1.0, query_failed=False,
    )
    assert result.score == 100.0
    assert result.grade == "A"
    assert result.version == HEALTH_SCORE_VERSION


def test_golden_file_known_deductions():
    """Fixed input -> fixed expected output. Any future formula edit must show up as a
    deliberate diff here, not silently change historical scores (UPGRADE_PLAN.md C.3)."""
    result = compute_health_score_from_values(
        teff_disagreement=300.0,   # -15.0 (300/20)
        rad_disagreement=0.1,      # -2.0 (0.1/0.05)
        dist_disagreement=50.0,    # -5.0 (50/10)
        ruwe=1.8,                  # -15.0 (>1.4)
        is_unphysical_rp=False,
        completeness_score=0.8,    # -4.0 ((1-0.8)*20)
        query_failed=False,
    )
    # 100 - 15 - 2 - 5 - 15 - 4 = 59.0; D-grade floor is 60 (the alert_engine.py value,
    # chosen as the base formula per UPGRADE_PLAN.md C.3), so 59.0 grades F.
    assert result.score == 59.0
    assert result.grade == "F"


def test_unphysical_and_query_failed_stack():
    result = compute_health_score_from_values(
        teff_disagreement=0.0, rad_disagreement=0.0, dist_disagreement=0.0,
        ruwe=1.0, is_unphysical_rp=True, completeness_score=1.0, query_failed=True,
    )
    # 100 - 25 (unphysical) - 15 (query_failed) = 60.0
    assert result.score == 60.0
    assert result.grade == "D"


def test_score_never_goes_negative():
    result = compute_health_score_from_values(
        teff_disagreement=10000.0, rad_disagreement=10.0, dist_disagreement=10000.0,
        ruwe=5.0, is_unphysical_rp=True, completeness_score=0.0, query_failed=True,
    )
    assert result.score == 0.0
    assert result.grade == "F"


def test_deductions_are_capped_not_unbounded():
    capped = compute_health_score_from_values(
        teff_disagreement=100000.0, rad_disagreement=0.0, dist_disagreement=0.0,
        ruwe=1.0, is_unphysical_rp=False, completeness_score=1.0, query_failed=False,
    )
    # teff cap is 20 points regardless of how large the mismatch is
    assert capped.score == 80.0
