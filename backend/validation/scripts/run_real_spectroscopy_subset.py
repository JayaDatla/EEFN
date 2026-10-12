"""
UPGRADE_PLAN.md F.7: run real APOGEE-2 DR17 spectroscopy cross-matching against a
small subset of real host stars and persist results with honest provenance
(`spectroscopy_is_real=True`, `spectroscopy_source`, `spectroscopy_computed_at`).

APOGEE has limited sky coverage -- most stars will get no match, which is the
correct, honest outcome (F.7's own note: "these surveys have limited sky coverage;
the pipeline must degrade gracefully"). Run manually:

    python validation/scripts/run_real_spectroscopy_subset.py --limit 20

Writes a JSON coverage report to backend/app/ml/spectroscopy_subset_report.json.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.session import SessionLocal
from app.db.models import HostStar
from app.pipeline.real_sync import sync_real_spectroscopy
from app.pipeline.spectroscopy import APOGEE_DR17_CATALOG


def run(limit: int) -> dict:
    db = SessionLocal()
    try:
        summary = sync_real_spectroscopy(db, limit=limit)
        total = db.query(HostStar).filter(HostStar.spectroscopy_is_real.is_(True)).count()
    finally:
        db.close()

    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "catalog": APOGEE_DR17_CATALOG,
        "attempted_this_run": summary["attempted"],
        "matched_this_run": summary["matched"],
        "results_this_run": summary["results"],
        "total_hosts_with_real_spectroscopy": total,
        "note": (
            "APOGEE-2 is a targeted spectroscopic survey with limited sky coverage, not "
            "all-sky -- a low match rate is the expected, honest result, not a bug."
        ),
    }
    report_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "app", "ml", "spectroscopy_subset_report.json",
    )
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote report to {report_path}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    run(args.limit)
