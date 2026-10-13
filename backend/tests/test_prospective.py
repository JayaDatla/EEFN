"""The pre-registered prospective test must be impossible to pass by accident or by tuning."""
import os
import random
import sys
from types import SimpleNamespace

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from app.science.flags import any_core_flag, compute_flags
from app.science.prospective import MIN_RESOLVED, evaluate, risk_difference_ci, wilson_interval

FLAGS = ["ruwe_likely_binary", "unphysical_radius"]


def _rows(n, flagged_fp_rate, clean_fp_rate, seed=0):
    rng = random.Random(seed)
    rows, disp = [], {}
    for i in range(n):
        flagged = i % 2 == 0
        toi = f"{1000 + i}.01"
        rows.append({"toi": toi, "flags": {"ruwe_likely_binary": flagged, "unphysical_radius": False},
                     "any_core_flag": flagged})
        fp = rng.random() < (flagged_fp_rate if flagged else clean_fp_rate)
        disp[toi] = "FP" if fp else "CP"
    return rows, disp


def test_an_informative_flag_is_supported():
    rows, disp = _rows(400, flagged_fp_rate=0.8, clean_fp_rate=0.3)
    out = evaluate(rows, disp, FLAGS)
    assert out["conclusion_allowed"] and out["verdict"].startswith("SUPPORTED")
    assert out["per_flag"]["any_core_flag"]["risk_difference_ci95"][0] > 0


def test_a_useless_flag_is_not_supported():
    rows, disp = _rows(400, flagged_fp_rate=0.5, clean_fp_rate=0.5, seed=3)
    assert evaluate(rows, disp, FLAGS)["verdict"].startswith("NOT SUPPORTED")


def test_too_few_resolved_candidates_draws_no_conclusion_even_if_the_flag_looks_perfect():
    rows, disp = _rows(100, flagged_fp_rate=1.0, clean_fp_rate=0.0)
    for r in rows[MIN_RESOLVED - 10:]:
        disp[r["toi"]] = "PC"                     # still unresolved
    out = evaluate(rows, disp, FLAGS)
    assert out["conclusion_allowed"] is False and out["verdict"].startswith("TOO EARLY")


def test_unresolved_and_withdrawn_candidates_are_never_counted_as_outcomes():
    rows = [{"toi": "1.01", "flags": {"ruwe_likely_binary": True, "unphysical_radius": False}, "any_core_flag": True},
            {"toi": "2.01", "flags": {"ruwe_likely_binary": False, "unphysical_radius": False}, "any_core_flag": False},
            {"toi": "3.01", "flags": {"ruwe_likely_binary": True, "unphysical_radius": False}, "any_core_flag": True}]
    out = evaluate(rows, {"1.01": "FP", "2.01": "PC"}, FLAGS)         # 3.01 is absent -> withdrawn
    assert out["n_resolved"] == 1 and out["n_still_unresolved"] == 1 and out["n_withdrawn_excluded"] == 1


def test_missing_flag_values_are_reported_as_not_checkable_not_as_clean():
    rows = [{"toi": f"{i}.01", "flags": {"ruwe_likely_binary": None, "unphysical_radius": False}, "any_core_flag": None}
            for i in range(5)]
    out = evaluate(rows, {r["toi"]: "FP" for r in rows}, FLAGS)
    assert out["per_flag"]["ruwe_likely_binary"]["n_not_checkable"] == 5
    assert out["per_flag"]["ruwe_likely_binary"]["n_clean"] == 0


def test_intervals_are_sane():
    lo, hi = wilson_interval(8, 10)
    assert 0.4 < lo < 0.8 < hi < 1.0
    ci = risk_difference_ci(40, 50, 10, 50)
    assert ci[0] > 0.3 and ci[1] < 0.9


def _host(**kw):
    base = dict(ruwe=None, rad=None, mass=None, teff=None, toi_teff=None, toi_rad=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _cand(**kw):
    base = dict(trandep=1000.0, orbper=4.0, trandurh=3.0)
    base.update(kw)
    return SimpleNamespace(**base)


def test_flags_are_none_when_inputs_are_missing_and_booleans_when_checkable():
    f = compute_flags(_cand(), _host())
    assert f["ruwe_likely_binary"] is None and f["unphysical_radius"] is None and f["teff_outlier"] is None
    f = compute_flags(_cand(), _host(ruwe=1.8, rad=1.0, teff=5000.0, toi_teff=5600.0, toi_rad=1.6))
    assert f["ruwe_likely_binary"] is True and f["ruwe_possible_binary"] is True
    assert f["teff_outlier"] is True and f["radius_outlier"] is True
    assert f["unphysical_radius"] is False
    f = compute_flags(_cand(trandep=250000.0), _host(rad=5.0))              # sqrt(0.25)*5*109 ~ 273 R_Earth
    assert f["unphysical_radius"] is True


def test_ruwe_tiers_nest():
    f = compute_flags(_cand(), _host(ruwe=1.3))
    assert f["ruwe_possible_binary"] is True and f["ruwe_likely_binary"] is False


def test_any_core_flag_is_false_only_when_something_was_checked_clean():
    assert any_core_flag({"ruwe_likely_binary": True}) is True
    assert any_core_flag({"ruwe_likely_binary": False, "unphysical_radius": None}) is False
    assert any_core_flag({k: None for k in ["ruwe_likely_binary", "unphysical_radius"]}) is None
