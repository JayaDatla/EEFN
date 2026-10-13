import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.api.endpoints import _ML_DIR
from main import app

client = TestClient(app)


def test_honest_evaluation_is_served_from_the_artifact_and_reports_the_baseline():
    r = client.get("/api/v1/predictions/honest_evaluation")
    assert r.status_code == 200
    data = r.json()
    with open(os.path.normpath(os.path.join(_ML_DIR, "honest_evaluation_report.json"))) as f:
        assert data["headline"] == json.load(f)["headline"]

    g = data["protocols"]["star_grouped_5fold"]
    assert g["toi_only_baseline"]["roc_auc"] > 0.5          # the baseline is always reported next to the full model
    lo, hi = g["ci95_by_star"]["auc_full"]
    assert lo < g["full_model"]["roc_auc"] < hi             # intervals bracket the point estimate
    assert any(k.startswith("time_forward") for k in data["protocols"])


def test_time_forward_is_reported_and_no_better_than_the_random_split():
    """The whole point of the protocol: scoring new candidates is harder than recovering labels
    for TOIs like the training ones. If this ever flips, the evaluation itself is suspect."""
    p = client.get("/api/v1/predictions/honest_evaluation").json()["protocols"]
    random_auc = p["random_stratified_5fold"]["full_model"]["roc_auc"]
    for name, s in p.items():
        if name.startswith("time_forward"):
            assert s["full_model"]["roc_auc"] < random_auc
