import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.science.health import grade_from_probability
from main import app

REPORT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "ml", "split_validation_report.json")


def test_grade_bands_are_the_fixed_a_priori_cuts():
    assert [grade_from_probability(p) for p in (0.95, 0.90, 0.80, 0.60, 0.30, 0.10)] == ["A", "A", "B", "C", "D", "F"]


def test_served_grade_matches_the_stored_model_probability():
    client = TestClient(app)
    rows = client.get("/api/v1/candidates?limit=50").json()
    rows = rows["items"] if isinstance(rows, dict) else rows
    checked = 0
    for r in rows:
        prof = client.get(f"/api/v1/candidates/{r['toi_id']}").json()
        p = (prof.get("prediction") or {}).get("evidence_consistency_score")
        if p is None or prof["health"]["version"] != "2.0.0-model":
            continue
        assert prof["health"]["grade"] == grade_from_probability(p)
        checked += 1
    if checked == 0:
        import pytest
        pytest.skip('no model-graded candidates in this database (fresh CI DB)')


def test_model_grade_a_is_cleaner_than_hand_grade_a_on_held_out_stars():
    """The reason the grade was switched: on stars the model never trained on, the model's A bucket must
    have a far lower false-positive share than the old hand-weighted A, under every protocol."""
    with open(REPORT, encoding="utf-8") as f:
        rep = json.load(f)
    assert len(rep["grade"]) >= 3
    for name, s in rep["grade"].items():
        old_a, new_a = s["old_hand_grade"]["A"], s["model_grade"]["A"]
        assert new_a["n"] >= 30, name
        assert new_a["false_positive_share"] < old_a["false_positive_share"] - 0.10, name
        assert s["auc_model_probability"] > s["auc_old_hand_grade"] + 0.10, name


def test_health_validation_separates_out_of_sample_from_in_sample():
    d = TestClient(app).get("/api/v1/health/validation").json()
    assert "in_sample_warning" in d
    assert d["out_of_sample"] is not None and "star_grouped_5fold" in d["out_of_sample"]["protocols"]


def test_flags_are_more_often_false_positives_on_held_out_data():
    d = TestClient(app).get("/api/v1/predictions/flag_validation").json()
    for name, s in d["protocols"].items():
        a = s["per_flag"]["any_core_flag"]
        assert a["risk_difference"] > 0.2 and a["risk_difference_ci95"][0] > 0, name


def test_profile_exposes_rule_based_checks_without_the_model():
    prof = TestClient(app).get("/api/v1/candidates?limit=1").json()
    rows = prof["items"] if isinstance(prof, dict) else prof
    if not rows:
        import pytest
        pytest.skip("empty database")
    cc = TestClient(app).get(f"/api/v1/candidates/{rows[0]['toi_id']}").json()["catalog_checks"]
    assert set(cc["core_flags"]) <= set(cc["flags"])
    assert cc["flags"]["evidence_score_low"] is None          # the model-derived flag is excluded here
    assert 0 <= cc["n_core_checkable"] <= len(cc["core_flags"])
    if cc["n_core_checkable"] == 0:
        assert cc["any_core_flag"] is None                      # nothing checkable is never reported clean
