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
from app.pipeline.spectroscopy import fetch_real_spectroscopy, APOGEE_DR17_CATALOG


def run(limit: int) -> dict:
    db = SessionLocal()
    stars = (
        db.query(HostStar)
        .filter(HostStar.spectroscopy_is_real.is_(False))
        .order_by(HostStar.hostname.asc())
        .limit(limit)
        .all()
    )

    results = []
    for star in stars:
        spec = fetch_real_spectroscopy(star.ra, star.dec)
        if not spec:
            results.append({"hostname": star.hostname, "status": "no_match"})
            continue

        if spec.teff_spec is not None:
            star.teff_spec = spec.teff_spec
        if spec.fe_h is not None:
            star.fe_h = spec.fe_h
        star.spectroscopy_is_real = True
        star.spectroscopy_source = f"APOGEE-2 DR17 (VizieR {APOGEE_DR17_CATALOG})"
        star.spectroscopy_computed_at = datetime.now(timezone.utc)
        db.add(star)
        db.commit()

        print(f"{star.hostname}: teff_spec={spec.teff_spec} fe_h={spec.fe_h} logg={spec.logg_spec}")
        results.append({
            "hostname": star.hostname, "status": "matched",
            "teff_spec": spec.teff_spec, "fe_h": spec.fe_h, "logg_spec": spec.logg_spec,
        })

    db.close()

    total_real = db_count_real_spectroscopy()
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "catalog": APOGEE_DR17_CATALOG,
        "attempted_this_run": len(results),
        "matched_this_run": sum(1 for r in results if r["status"] == "matched"),
        "results_this_run": results,
        "total_hosts_with_real_spectroscopy": total_real,
        "note": (
            "APOGEE-2 is a targeted spectroscopic survey with limited sky coverage, not "
            "all-sky -- a low match rate here is the expected, honest result, not a bug. "
            "spectroscopy_is_real=True on a host star means teff_spec/fe_h came from a real "
            "VizieR query against APOGEE-2 DR17, not seed_db.py's fabricated demo values."
        ),
    }

    report_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "app", "ml", "spectroscopy_subset_report.json",
    )
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nWrote report to {report_path}")
    return report


def db_count_real_spectroscopy() -> int:
    db = SessionLocal()
    try:
        return db.query(HostStar).filter(HostStar.spectroscopy_is_real.is_(True)).count()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    run(args.limit)
