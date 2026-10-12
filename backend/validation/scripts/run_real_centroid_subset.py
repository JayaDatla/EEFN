"""
UPGRADE_PLAN.md F.6: run real MAST TPF centroid extraction against a small subset of
real ingested candidates and persist the results with honest provenance
(`centroid_is_real=True`, `centroid_sector`, `centroid_computed_at`).

Now a thin wrapper over app.pipeline.real_sync.sync_real_centroids, which the Arq worker also
runs nightly (app/worker.py). Use this for an immediate manual batch:

    python validation/scripts/run_real_centroid_subset.py --limit 5

Writes a JSON coverage report to backend/app/ml/centroid_subset_report.json so the
actual, current coverage is documented rather than implied.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.session import SessionLocal
from app.db.models import ExoplanetCandidate
from app.pipeline.real_sync import sync_real_centroids


def run(limit: int) -> dict:
    db = SessionLocal()
    try:
        summary = sync_real_centroids(db, limit=limit)
        total = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.centroid_is_real.is_(True)).count()
    finally:
        db.close()

    for r in summary["results"]:
        print(r)
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "attempted_this_run": summary["attempted"],
        "measured_this_run": summary["measured"],
        "results_this_run": summary["results"],
        "total_candidates_with_real_centroid": total,
        "note": (
            "centroid_is_real=True means centroid_shift_max/has_centroid_dip came from an actual "
            "downloaded MAST TPF (aperture centroids, per-event local baseline, empirical "
            "fake-epoch null for the significance), not seed_db.py's fabricated demo values."
        ),
    }
    report_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "app", "ml", "centroid_subset_report.json",
    )
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"
Wrote report to {report_path}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    run(args.limit)
