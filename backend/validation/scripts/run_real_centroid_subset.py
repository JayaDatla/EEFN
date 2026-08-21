"""
UPGRADE_PLAN.md F.6: run real MAST TPF centroid extraction against a small subset of
real ingested candidates and persist the results with honest provenance
(`centroid_is_real=True`, `centroid_sector`, `centroid_computed_at`).

Deliberately NOT run automatically as part of the main ingestion pipeline (D.2) --
TPF downloads are GB-scale per target and this needs its own caching/storage design
before it can run at full catalog scale. Run manually:

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
from app.pipeline.mast_centroid import fetch_transit_epoch, compute_real_centroid_offset


def run(limit: int) -> dict:
    db = SessionLocal()
    candidates = (
        db.query(ExoplanetCandidate)
        .filter(ExoplanetCandidate.tic_id.isnot(None))
        .filter(ExoplanetCandidate.orbper.isnot(None))
        .filter(ExoplanetCandidate.trandurh.isnot(None))
        .filter(ExoplanetCandidate.centroid_is_real.is_(False))
        .order_by(ExoplanetCandidate.toi_id.asc())
        .limit(limit)
        .all()
    )

    results = []
    for cand in candidates:
        print(f"--- TOI-{cand.toi_id} (TIC {cand.tic_id}) ---")
        epoch_row = fetch_transit_epoch(cand.tic_id)
        if not epoch_row:
            print("  No transit epoch available from NASA TAP -- skipping.")
            results.append({"toi_id": cand.toi_id, "tic_id": cand.tic_id, "status": "no_epoch"})
            continue

        centroid = compute_real_centroid_offset(
            tic_id=cand.tic_id,
            period_days=cand.orbper,
            duration_hours=cand.trandurh,
            epoch_bjd=epoch_row["pl_tranmid"],
        )
        if not centroid:
            print("  No real centroid measurement available (no TPF / download failed / insufficient coverage).")
            results.append({"toi_id": cand.toi_id, "tic_id": cand.tic_id, "status": "no_measurement"})
            continue

        cand.centroid_shift_max = centroid.offset_arcsec
        cand.centroid_significance_sigma = centroid.significance_sigma
        cand.has_centroid_dip = centroid.significance_sigma >= 3.0
        cand.centroid_is_real = True
        cand.centroid_sector = centroid.sector
        cand.centroid_computed_at = datetime.now(timezone.utc)
        cand.centroid_dx_json = centroid.dx_binned
        cand.centroid_dy_json = centroid.dy_binned
        db.add(cand)
        db.commit()

        print(
            f"  offset={centroid.offset_arcsec:.4f}\" sigma={centroid.significance_sigma:.2f} "
            f"sector={centroid.sector} n_in={centroid.n_in_transit} n_out={centroid.n_out_of_transit}"
        )
        results.append({
            "toi_id": cand.toi_id, "tic_id": cand.tic_id, "status": "measured",
            "offset_arcsec": centroid.offset_arcsec, "significance_sigma": centroid.significance_sigma,
            "sector": centroid.sector,
        })

    db.close()

    total_real_centroid = db_count_real_centroid()
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "attempted_this_run": len(results),
        "measured_this_run": sum(1 for r in results if r["status"] == "measured"),
        "results_this_run": results,
        "total_candidates_with_real_centroid": total_real_centroid,
        "note": (
            "This is a small, manually-run verification subset (UPGRADE_PLAN.md F.6), not "
            "full-catalog coverage. centroid_is_real=True on a candidate means its "
            "centroid_shift_max/has_centroid_dip came from an actual downloaded MAST TPF, "
            "not seed_db.py's fabricated demo values."
        ),
    }

    report_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "app", "ml", "centroid_subset_report.json",
    )
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nWrote report to {report_path}")
    return report


def db_count_real_centroid() -> int:
    db = SessionLocal()
    try:
        return db.query(ExoplanetCandidate).filter(ExoplanetCandidate.centroid_is_real.is_(True)).count()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    run(args.limit)
