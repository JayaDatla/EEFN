import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from app.science.health_validation import validate_health
from main import app


def _rows():
    rows = []
    for i in range(40):
        rows.append({"disposition": "CP", "health_score": 90 - i % 5, "health_grade": "A"})
    for i in range(20):
        rows.append({"disposition": "FP", "health_score": 90 - i % 5, "health_grade": "A"})   # grade A is 1/3 FP
    for i in range(30):
        rows.append({"disposition": "FP", "health_score": 30 - i % 5, "health_grade": "F"})
    rows.append({"disposition": "PC", "health_score": 80, "health_grade": "B"})                # unresolved: ignored
    rows.append({"disposition": "CP", "health_score": None, "health_grade": None})            # unscored: ignored
    return rows


def test_grade_false_positive_share_is_reported_per_grade_against_the_base_rate():
    out = validate_health(_rows())
    assert out["n_labelled"] == 90
    assert out["by_grade"]["A"]["n"] == 60 and out["by_grade"]["A"]["false_positive_share"] == pytest.approx(1 / 3)
    assert out["by_grade"]["F"]["false_positive_share"] == 1.0
    assert out["by_grade"]["B"]["n"] == 0 and out["by_grade"]["B"]["false_positive_share"] is None
    assert out["base_rate_false_positive"] == pytest.approx(50 / 90)


def test_auc_ranks_planets_above_false_positives():
    out = validate_health(_rows())
    assert 0.7 < out["auc_planet_vs_false_positive"] < 1.0


def test_no_labelled_rows_gives_none_not_a_number():
    out = validate_health([{"disposition": "PC", "health_score": 50, "health_grade": "C"}])
    assert out["auc_planet_vs_false_positive"] is None and out["base_rate_false_positive"] is None


def test_endpoint_returns_live_validation():
    data = TestClient(app).get("/api/v1/health/validation").json()
    assert set(data["by_grade"]) == set("ABCDF")
    if data["n_labelled"] == 0:            # empty database (e.g. CI): shape only, nothing to validate
        assert data["auc_planet_vs_false_positive"] is None
        return
    assert 0.0 <= data["auc_planet_vs_false_positive"] <= 1.0
