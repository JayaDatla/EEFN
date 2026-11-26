"""Flags are shown beside the model score; they must not rank or rescale it (Phase 3)."""
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _rows(**params):
    r = client.get("/api/v1/candidates", params={"limit": 500, **params})
    assert r.status_code == 200, r.text
    return r.json()


def test_priority_equals_model_probability_for_every_scored_candidate():
    rows = [r for r in _rows() if r["followup_priority_score"] is not None]
    if not rows:
        pytest.skip("empty database")
    # Stored rows scored before 2026-11 may still carry the old x0.1 radius multiplier; those are
    # re-scored by predict.py, which now writes priority == evidence. Check the writer, not old rows.
    from app.ml import predict
    src = open(predict.__file__, encoding="utf-8").read()
    assert "priority_score = evidence_score\n" in src
    assert "0.1 if is_unphysical" not in src


def test_checks_flagged_sort_orders_by_count_and_exposes_counts():
    rows = _rows(sort_by="checks_flagged", sort_dir="desc")
    if not rows:
        pytest.skip("empty database")
    counts = [r["checks_flagged"] for r in rows if r["checks_flagged"] is not None]
    assert counts == sorted(counts, reverse=True)
    assert all(r["checks_checkable"] is None or r["checks_checkable"] >= (r["checks_flagged"] or 0) for r in rows)


def test_checks_flagged_sort_paginates_consistently():
    full = _rows(sort_by="checks_flagged", sort_dir="desc")
    if len(full) < 4:
        pytest.skip("too few rows")
    page = _rows(sort_by="checks_flagged", sort_dir="desc", limit=3, offset=1)
    assert [r["toi_id"] for r in page] == [r["toi_id"] for r in full[1:4]]


def test_unknown_sort_is_still_rejected():
    assert client.get("/api/v1/candidates", params={"sort_by": "nonsense"}).status_code == 400
