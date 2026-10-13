"""
One-off backfill after the train/serve skew fix: store the TOI table's own host-star values
(st_teff / st_rad / st_dist / st_logg) on every existing HostStar, then re-score every
candidate so stored evidence-consistency scores reflect the corrected inputs and carry the
model version that produced them.

New ingestion runs persist these columns themselves (app/pipeline/ingest.py); this only repairs
rows ingested before that. One NASA TAP request, no per-target calls.

    python validation/scripts/backfill_toi_stellar_params.py [--dry-run]
"""
import argparse
import os
import sys
import time

import numpy as np
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.models import ExoplanetCandidate, HostStar, MLPrediction  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.ml.predict import predictor  # noqa: E402

NASA_TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
# Lower-case and without "IS NOT NULL": the archive's firewall has answered 403 to the upper-case
# form of similar queries (see validation/scripts/leakage_rv_confirmed_holdout.py).
QUERY = "select tid, st_teff, st_rad, st_dist, st_logg from toi"


def fetch_toi_stellar_values(attempts: int = 4) -> dict:
    last = None
    for i in range(attempts):
        try:
            r = requests.get(NASA_TAP_URL, params={"query": QUERY, "format": "json"}, timeout=90)
            r.raise_for_status()
            out = {}
            for row in r.json():
                cur = out.setdefault(int(row["tid"]), {})
                for k in ("st_teff", "st_rad", "st_dist", "st_logg"):
                    if cur.get(k) is None and row.get(k) is not None:
                        cur[k] = float(row[k])
            return out
        except Exception as e:   # archive timeouts are common; back off and retry
            last = e
            time.sleep(5 * (i + 1))
    raise SystemExit(f"NASA TAP unreachable after {attempts} attempts: {last}")


def main(dry_run: bool) -> None:
    toi = fetch_toi_stellar_values()
    print(f"Fetched TOI stellar values for {len(toi)} TICs.")

    db = SessionLocal()
    try:
        hosts = db.query(HostStar).all()
        updated = unmatched = 0
        for h in hosts:
            try:
                tic = int(h.hostname.replace("TIC", "").strip())
            except ValueError:
                unmatched += 1
                continue
            vals = toi.get(tic)
            if not vals:
                unmatched += 1
                continue
            h.toi_teff, h.toi_rad = vals.get("st_teff"), vals.get("st_rad")
            h.toi_dist, h.toi_logg = vals.get("st_dist"), vals.get("st_logg")
            updated += 1
        print(f"Hosts updated: {updated}; no TOI row (seed/test hosts): {unmatched}")
        if dry_run:
            db.rollback()
            print("Dry run: nothing written.")
            return
        db.commit()

        before = {p.candidate_id: p.evidence_consistency_score for p in db.query(MLPrediction).all()}
        scored = 0
        for cand in db.query(ExoplanetCandidate).all():
            res = predictor.predict_confirmation(cand.id, db)
            if res.get("status") == "success":
                scored += 1
        after = {p.candidate_id: p.evidence_consistency_score for p in db.query(MLPrediction).all()}
        both = [k for k in after if k in before]
        delta = np.array([after[k] - before[k] for k in both])
        print(f"Re-scored {scored} candidates with model {predictor.model_version}.")
        if len(delta):
            print(f"Score change: mean {delta.mean():+.3f}, |mean| {np.abs(delta).mean():.3f}, "
                  f"max |change| {np.abs(delta).max():.3f}")
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    main(args.dry_run)
