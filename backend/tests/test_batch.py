import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _real_toi_ids(limit=2):
    res = client.get(f"/api/v1/candidates?limit={limit}")
    return [c["toi_id"] for c in res.json()]


def test_batch_audit_rejects_empty_list():
    res = client.post("/api/v1/batch/audit", json={"toi_ids": []})
    assert res.status_code == 400


def test_batch_audit_rejects_oversized_list():
    res = client.post("/api/v1/batch/audit", json={"toi_ids": [float(i) for i in range(501)]})
    assert res.status_code == 400


def test_batch_audit_reports_not_found_honestly():
    """UPGRADE_PLAN.md A.14: a TOI ID with no real match must be reported in
    not_found, never silently dropped or backfilled with a placeholder row."""
    res = client.post("/api/v1/batch/audit", json={"toi_ids": [999999.99]})
    assert res.status_code == 200
    data = res.json()
    assert data["requested_count"] == 1
    assert data["found_count"] == 0
    assert 999999.99 in data["not_found"]
    assert data["results"][0]["found"] is False
    assert data["results"][0]["pl_name"] is None


def test_batch_audit_real_candidates_match_individual_lookup():
    toi_ids = _real_toi_ids(2)
    if not toi_ids:
        return  # empty dev DB -- nothing to assert
    res = client.post("/api/v1/batch/audit", json={"toi_ids": toi_ids})
    assert res.status_code == 200
    data = res.json()
    assert data["found_count"] == len(toi_ids)

    single = client.get(f"/api/v1/candidates/{toi_ids[0]}").json()
    batch_row = next(r for r in data["results"] if r["toi_id"] == toi_ids[0])
    assert batch_row["health_grade"] == single["health"]["grade"]
    assert batch_row["model_tier"] == single["model_tier"]["tier"]


def test_batch_export_returns_votable_for_real_candidates():
    toi_ids = _real_toi_ids(2)
    if not toi_ids:
        return
    res = client.post("/api/v1/batch/export", json={"toi_ids": toi_ids})
    assert res.status_code == 200
    assert b"<VOTABLE" in res.content


def test_batch_export_rejects_empty_list():
    res = client.post("/api/v1/batch/export", json={"toi_ids": []})
    assert res.status_code == 400
