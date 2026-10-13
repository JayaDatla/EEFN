"""
Freeze a prospective snapshot: the catalog-hygiene flags (and scores) of every TOI that is still
UNRESOLVED (disposition PC) right now, BEFORE anyone knows how they will be dispositioned.

The snapshot is the pre-registration. Its SHA-256 is appended to prospective/MANIFEST.json, the file
is never overwritten, and prospective_evaluate.py refuses to use a snapshot whose hash no longer
matches. Thresholds come from app/science/flags.py and are embedded in the file; changing them means
taking a NEW snapshot, not re-scoring an old one.

    python validation/scripts/prospective_snapshot.py [--label first]

Commit the snapshot and the manifest (they are small) so their timestamps are in version history.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.models import ExoplanetCandidate, MLPrediction  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.ml.predict import predictor  # noqa: E402
from app.science.flags import CORE_FLAGS, THRESHOLDS, any_core_flag, compute_flags  # noqa: E402
from validation_helpers import current_dispositions  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "app", "ml", "prospective")


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def main(label: str) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc)
    path = os.path.join(OUT_DIR, f"snapshot_{stamp:%Y%m%d}_{label}.json")
    if os.path.exists(path):
        raise SystemExit(f"{path} already exists. Snapshots are immutable; choose a different --label or date.")

    # The database's dispositions date from its last sync; a TOI that has resolved since is no longer
    # a prediction target -- including it would let a known outcome into a pre-registered test.
    # So eligibility is decided by the archive's disposition RIGHT NOW (PC or APC = unresolved).
    now_disp = current_dispositions()
    db = SessionLocal()
    already_resolved = missing_from_archive = 0
    try:
        rows = []
        for cand in db.query(ExoplanetCandidate).order_by(ExoplanetCandidate.toi_id).all():
            key = f"{cand.toi_id:.2f}"
            if key not in now_disp:
                missing_from_archive += 1
                continue
            if now_disp[key] not in ("PC", "APC"):
                already_resolved += 1
                continue
            host = cand.host
            pred = db.query(MLPrediction).filter(MLPrediction.candidate_id == cand.id).first()
            flags = compute_flags(cand, host, pred)
            vet = cand.lc_vetting_json if cand.lc_vetting_status == "vetted" and cand.lc_vetting_json else None
            rows.append({
                "toi": key, "tic": cand.tic_id, "disposition_at_snapshot": now_disp[key],
                "flags": flags, "any_core_flag": any_core_flag(flags),
                "evidence_consistency_score": pred.evidence_consistency_score if pred else None,
                "centroid_is_dip": bool(cand.has_centroid_dip) if cand.centroid_is_real and cand.has_centroid_dip is not None else None,
                "lightcurve_best_class": vet["best_class"] if vet else None,
            })
    finally:
        db.close()

    snapshot = {
        "created_at": stamp.isoformat(), "label": label, "git_commit": git_commit(),
        "model_version": predictor.model_version, "thresholds": THRESHOLDS, "core_flags": CORE_FLAGS,
        "hypothesis": ("Among TOIs unresolved (PC) at this snapshot, those with >= 1 core catalog flag are more "
                       "likely to be later dispositioned FP/FA than those with none."),
        "n_candidates": len(rows), "excluded_already_resolved": already_resolved,
        "excluded_not_in_archive": missing_from_archive, "rows": rows,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=1, sort_keys=True)
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()

    manifest_path = os.path.join(OUT_DIR, "MANIFEST.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else []
    manifest.append({"file": os.path.basename(path), "sha256": digest, "created_at": stamp.isoformat(),
                     "n_candidates": len(rows), "git_commit": snapshot["git_commit"]})
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=1)

    flagged = sum(1 for r in rows if r["any_core_flag"] is True)
    clean = sum(1 for r in rows if r["any_core_flag"] is False)
    unk = len(rows) - flagged - clean
    print(f"Wrote {path}\n  {len(rows)} unresolved TOIs: {flagged} with >=1 core flag, {clean} clean, {unk} not checkable")
    print(f"  sha256 {digest}\nAppended to {manifest_path}. Commit both files.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="first")
    main(ap.parse_args().label)
