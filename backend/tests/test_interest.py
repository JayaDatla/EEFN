"""Observational novelty: a separate axis that must not leak into grades, checks or flags."""
import os

import pytest
from fastapi.testclient import TestClient

from app.science.interest import REFERENCE_CSV, novelty
from main import app

pytestmark = pytest.mark.skipif(not os.path.exists(REFERENCE_CSV), reason="interest reference not built")
client = TestClient(app)


def test_giant_planet_around_a_very_low_mass_star_is_more_novel_than_a_typical_hot_jupiter():
    typical = novelty(12.0, 3.5, 1.0)["novelty"]
    rare = novelty(12.0, 3.0, 0.15)["novelty"]
    assert 0 <= typical < 0.6
    assert rare > typical and rare > 0.9


def test_score_is_bounded_and_a_common_planet_scores_low():
    common = novelty(1.8, 10.0, 0.8)["novelty"]
    assert 0 <= common <= 1 and common < 0.4


def test_missing_or_unphysical_inputs_give_none_with_a_reason_never_zero():
    for args in [(None, 3.0, 1.0), (5.0, None, 1.0), (5.0, 3.0, None), (-1.0, 3.0, 1.0), (30.0, 3.0, 1.0)]:
        out = novelty(*args)
        assert out["novelty"] is None and out["reason"]


def test_candidate_list_sorts_by_novelty_and_exposes_it():
    rows = client.get("/api/v1/candidates", params={"sort_by": "interest_novelty", "sort_dir": "desc",
                                                    "limit": 200}).json()
    if not rows:
        pytest.skip("empty database")
    vals = [r["interest_novelty"] for r in rows if r["interest_novelty"] is not None]
    assert vals == sorted(vals, reverse=True)
    # candidates that cannot be scored come last, not first
    first_none = next((i for i, r in enumerate(rows) if r["interest_novelty"] is None), len(rows))
    assert all(r["interest_novelty"] is None for r in rows[first_none:])


def test_novelty_does_not_change_grade_or_checks():
    rows = client.get("/api/v1/candidates", params={"limit": 20}).json()
    if not rows:
        pytest.skip("empty database")
    a = client.get("/api/v1/candidates", params={"limit": 20, "sort_by": "toi_id"}).json()
    b = client.get("/api/v1/candidates", params={"limit": 20, "sort_by": "interest_novelty"}).json()
    by_a = {r["toi_id"]: (r["health_grade"], r["checks_flagged"]) for r in a}
    for r in b:
        if r["toi_id"] in by_a:
            assert by_a[r["toi_id"]] == (r["health_grade"], r["checks_flagged"])


def test_profile_has_scientific_interest_block_and_csv_column():
    rows = client.get("/api/v1/candidates", params={"limit": 1}).json()
    if not rows:
        pytest.skip("empty database")
    prof = client.get(f"/api/v1/candidates/{rows[0]['toi_id']}").json()
    assert "novelty" in prof["scientific_interest"]
    head = client.get("/api/v1/candidates/export", params={"format": "csv", "limit": 1}).text.splitlines()[0]
    assert "interest_novelty" in head
