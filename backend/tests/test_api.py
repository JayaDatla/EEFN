import pytest
from fastapi.testclient import TestClient
import os
import sys

# Ensure backend directory is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"

def test_get_candidates():
    response = client.get("/api/v1/candidates")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        cand = data[0]
        assert "pl_name" in cand
        assert "tic_id" in cand
        assert "toi_id" in cand
        assert "disposition" in cand

def test_get_candidate_detail():
    # Let's first fetch a valid TOI ID from candidates list
    response = client.get("/api/v1/candidates")
    assert response.status_code == 200
    cands = response.json()
    
    if len(cands) > 0:
        toi_id = cands[0]["toi_id"]
        detail_response = client.get(f"/api/v1/candidates/{toi_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert "planet" in detail
        assert "star" in detail
        assert "agreement_metrics" in detail
        assert "prediction" in detail
        
        # Verify nested structures
        assert detail["planet"]["toi_id"] == toi_id
        assert "teff_disagreement" in detail["agreement_metrics"]
        assert "evidence_consistency_score" in detail["prediction"]
    else:
        # If no candidates ingested, test 404 behavior
        detail_response = client.get("/api/v1/candidates/9999.99")
        assert detail_response.status_code == 404

def test_get_model_metrics():
    """UPGRADE_PLAN.md A.8/C.8: metrics must come from a real evaluation artifact
    (model_metrics.json), not a hardcoded dict in the endpoint."""
    import json
    from app.api.endpoints import _MODEL_METRICS_PATH

    response = client.get("/api/v1/predictions/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["model_type"] == "Random Forest Classifier"
    assert "metrics" in data
    assert "accuracy" in data["metrics"]
    assert "evaluated_at" in data
    assert "dataset_sha256_16" in data

    with open(os.path.normpath(_MODEL_METRICS_PATH)) as f:
        on_disk = json.load(f)
    assert data == on_disk


def test_get_model_metrics_returns_503_when_artifact_missing(monkeypatch):
    from app.api import endpoints

    monkeypatch.setattr(endpoints, "_MODEL_METRICS_PATH", "/nonexistent/model_metrics.json")
    response = client.get("/api/v1/predictions/metrics")
    assert response.status_code == 503


def test_get_model_calibration():
    """UPGRADE_PLAN.md E.2: calibration must come from a real held-out evaluation
    (reliability diagram + Brier score), not a hardcoded/fabricated dict."""
    import json
    from app.api.endpoints import _CALIBRATION_REPORT_PATH

    response = client.get("/api/v1/predictions/calibration")
    assert response.status_code == 200
    data = response.json()
    assert "brier_score" in data
    assert 0.0 <= data["brier_score"] <= 1.0
    assert "reliability_bins" in data
    assert len(data["reliability_bins"]) == 10
    for b in data["reliability_bins"]:
        assert "count" in b and "bin_lower" in b and "bin_upper" in b
        if b["count"] == 0:
            assert b["observed_frequency"] is None
        else:
            assert 0.0 <= b["observed_frequency"] <= 1.0

    with open(os.path.normpath(_CALIBRATION_REPORT_PATH)) as f:
        on_disk = json.load(f)
    assert data == on_disk


def test_get_model_calibration_returns_503_when_artifact_missing(monkeypatch):
    from app.api import endpoints

    monkeypatch.setattr(endpoints, "_CALIBRATION_REPORT_PATH", "/nonexistent/calibration_report.json")
    response = client.get("/api/v1/predictions/calibration")
    assert response.status_code == 503

def test_get_graph_data():
    nodes_res = client.get("/api/v1/graph/nodes")
    edges_res = client.get("/api/v1/graph/edges")
    assert nodes_res.status_code == 200
    assert edges_res.status_code == 200
    assert isinstance(nodes_res.json(), list)
    assert isinstance(edges_res.json(), list)

def test_quality_endpoints():
    response = client.get("/api/v1/candidates")
    assert response.status_code == 200
    cands = response.json()
    if len(cands) > 0:
        toi_id = cands[0]["toi_id"]
        
        # Test Alerts
        alerts_res = client.get(f"/api/v1/candidates/{toi_id}/alerts")
        assert alerts_res.status_code == 200
        assert isinstance(alerts_res.json(), list)
        
        # Test Health
        health_res = client.get(f"/api/v1/candidates/{toi_id}/health")
        assert health_res.status_code == 200
        health = health_res.json()
        assert "health_score" in health
        assert "health_grade" in health
        
        # Test Resolution
        res_res = client.get(f"/api/v1/candidates/{toi_id}/resolution")
        assert res_res.status_code == 200
        assert "gaia_matched" in res_res.json()
        
        # Test Override
        override_res = client.post(f"/api/v1/candidates/{toi_id}/resolution/override", json={"gaia_id": "123456789"})
        assert override_res.status_code == 200
        assert override_res.json()["status"] == "success"
        
        # Test Timeline
        tl_res = client.get(f"/api/v1/candidates/{toi_id}/timeline")
        assert tl_res.status_code == 200
        assert isinstance(tl_res.json(), list)

        # Test Transit Pipeline
        tp_res = client.get(f"/api/v1/candidates/{toi_id}/transit_pipeline")
        assert tp_res.status_code == 200
        tp_data = tp_res.json()
        assert "time" in tp_data
        assert "raw_flux" in tp_data
        assert "detrended_flux" in tp_data
        assert "classification" in tp_data
        assert "metrics" in tp_data

def test_get_catalog_health():
    res = client.get("/api/v1/catalog/health")
    assert res.status_code == 200
    data = res.json()
    assert "conflict_rate" in data
    assert "ingestion_success_rate" in data
    # Regression test for a real bug found while rebuilding the admin page (H.3.8):
    # ingestion_success_rate/cross_match_success_rate/stale_record_rate were
    # hardcoded constants (0.995, 0.984, 0.05) rather than computed from real
    # query_failed/updated_at data. A near-empty test DB's real success rate
    # should not coincidentally equal the old fabricated constant.
    assert data["ingestion_success_rate"] != 0.995 or data["total_candidates"] == 0
    assert data["stale_record_rate"] != 0.05 or data["total_candidates"] == 0


class _FakeArqJob:
    job_id = "fake-job-id-123"


class _FakeArqPool:
    async def enqueue_job(self, func_name, *args):
        return _FakeArqJob()


def test_pipeline_run_enqueues_a_real_job_row(monkeypatch):
    """UPGRADE_PLAN.md D.2: /pipeline/run must create a PipelineRun row with real
    status/history instead of firing a bare BackgroundTask into the void (A.9)."""
    from app.api import endpoints

    async def fake_get_arq_pool():
        return _FakeArqPool()

    monkeypatch.setattr(endpoints, "get_arq_pool", fake_get_arq_pool)

    response = client.post("/api/v1/pipeline/run?limit=7")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["limit_requested"] == 7
    assert data["arq_job_id"] == "fake-job-id-123"

    run_id = data["id"]
    detail = client.get(f"/api/v1/pipeline/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == run_id

    listing = client.get("/api/v1/pipeline/runs")
    assert listing.status_code == 200
    assert any(r["id"] == run_id for r in listing.json())


def test_pipeline_run_detail_404_for_unknown_id():
    response = client.get("/api/v1/pipeline/runs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_candidates_pagination_and_sorting(monkeypatch):
    """UPGRADE_PLAN.md D.3: /candidates must do real server-side pagination/sorting
    (the previous version pulled up to `limit` unordered rows and filtered
    client-side), and expose the total match count via X-Total-Count."""
    # The true total comes from X-Total-Count, not len(response) -- a `limit=500`
    # fetch's row count is only the real total when the DB has <=500 candidates.
    # This assumption silently held while the dev DB stayed under 500 rows and
    # broke the moment a real full re-sync grew it past that (found live, not
    # hypothetical: 546 candidates after ingest.py's toi-ordering fix let a sync
    # actually reach previously-unsynced TOIs).
    full = client.get("/api/v1/candidates?limit=500")
    assert full.status_code == 200
    assert "x-total-count" in {k.lower() for k in full.headers.keys()}
    total = int(full.headers["x-total-count"])
    if total < 2:
        pytest.skip("not enough seeded candidates to exercise pagination in this environment")

    resp = client.get("/api/v1/candidates?limit=2&sort_by=toi_id&sort_dir=asc")
    assert resp.status_code == 200
    assert "x-total-count" in {k.lower() for k in resp.headers.keys()}
    assert int(resp.headers["x-total-count"]) == total

    page1 = client.get("/api/v1/candidates?limit=2&offset=0&sort_by=toi_id&sort_dir=asc").json()
    page2 = client.get("/api/v1/candidates?limit=2&offset=2&sort_by=toi_id&sort_dir=asc").json()
    assert [c["toi_id"] for c in page1] != [c["toi_id"] for c in page2]

    ids_asc = [c["toi_id"] for c in client.get("/api/v1/candidates?limit=500&sort_by=toi_id&sort_dir=asc").json()]
    assert ids_asc == sorted(ids_asc)


def test_candidates_rejects_unknown_sort_field():
    response = client.get("/api/v1/candidates?sort_by=not_a_real_field")
    assert response.status_code == 400


def test_write_endpoints_require_api_key_when_configured(monkeypatch):
    """UPGRADE_PLAN.md D.3: write endpoints must reject requests without a valid
    X-API-Key once API_KEY is configured (main.py:24's old allow_origins=["*"] plus
    zero auth meant anyone who found a deployed instance could trigger unbounded
    external API load or overwrite curator decisions)."""
    from app.config import settings

    monkeypatch.setattr(settings, "API_KEY", "super-secret-test-key")

    no_key = client.post("/api/v1/candidates/1.01/resolution/override", json={"gaia_id": "1"})
    assert no_key.status_code == 401

    wrong_key = client.post(
        "/api/v1/candidates/1.01/resolution/override",
        json={"gaia_id": "1"},
        headers={"X-API-Key": "nope"},
    )
    assert wrong_key.status_code == 401

    # A read endpoint must remain unauthenticated even with API_KEY configured --
    # auth is scoped to write endpoints only, per the plan.
    read_resp = client.get("/api/v1/candidates?limit=1")
    assert read_resp.status_code == 200
