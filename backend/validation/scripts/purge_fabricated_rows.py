"""
Remove fabricated (seed_db.py) and orphaned rows from a database that also holds real ingested data.

A row is kept only if its host's TIC id appears in the NASA Exoplanet Archive TOI table (one TAP
request). Everything else -- seed_db.py's invented TICs, restored legacy orphans -- is reported and,
unless --dry-run, deleted together with its dependent rows. Real TOIs missing from the archive's
TOI table (withdrawn since ingestion) are also listed, so review the dry run before deleting.

    python validation/scripts/purge_fabricated_rows.py --dry-run
    python validation/scripts/purge_fabricated_rows.py
"""
import argparse
import os
import sys

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.models import (AgreementMetrics, DispositionChangeEvent, ExoplanetCandidate, HostStar,  # noqa: E402
                           MeasurementHistory, MLPrediction)
from app.db.session import SessionLocal  # noqa: E402

NASA_TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"


def real_tic_ids() -> set:
    r = requests.get(NASA_TAP_URL, params={"query": "select distinct tid from toi", "format": "json"}, timeout=90)
    r.raise_for_status()
    return {int(row["tid"]) for row in r.json()}


def main(dry_run: bool) -> None:
    real = real_tic_ids()
    print(f"NASA TOI table: {len(real)} distinct TICs.")
    db = SessionLocal()
    try:
        doomed_hosts = []
        for h in db.query(HostStar).all():
            try:
                tic = int(h.hostname.replace("TIC", "").strip())
            except ValueError:
                tic = None
            if tic is None or tic not in real:
                doomed_hosts.append(h)
        host_ids = [h.id for h in doomed_hosts]
        cands = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.host_id.in_(host_ids)).all() if host_ids else []
        cand_ids = [c.id for c in cands]
        print(f"Not in the TOI table: {len(doomed_hosts)} hosts, {len(cands)} candidates.")
        for c in cands[:8]:
            print("   ", c.pl_name, c.disposition, "TIC", c.tic_id)
        if dry_run or not doomed_hosts:
            print("Dry run: nothing deleted." if dry_run else "Nothing to delete.")
            return
        if cand_ids:
            for model in (MLPrediction, AgreementMetrics, MeasurementHistory, DispositionChangeEvent):
                db.query(model).filter(model.candidate_id.in_(cand_ids)).delete(synchronize_session=False)
            db.query(ExoplanetCandidate).filter(ExoplanetCandidate.id.in_(cand_ids)).delete(synchronize_session=False)
        db.query(HostStar).filter(HostStar.id.in_(host_ids)).delete(synchronize_session=False)
        db.commit()
        print(f"Deleted {len(doomed_hosts)} hosts and {len(cands)} candidates (and their dependent rows).")
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    main(ap.parse_args().dry_run)
