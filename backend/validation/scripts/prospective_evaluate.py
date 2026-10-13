"""
Judge a frozen snapshot against the dispositions the NASA Exoplanet Archive lists NOW.

Refuses to run if the snapshot's SHA-256 does not match prospective/MANIFEST.json (a snapshot edited
after the fact is not a pre-registration). Draws a conclusion only once enough candidates have
resolved (app/science/prospective.py: >= 60 resolved, >= 10 per arm); before that it reports
progress and says TOO EARLY.

    python validation/scripts/prospective_evaluate.py snapshot_20261013_first.json
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.science.prospective import evaluate  # noqa: E402
from validation_helpers import current_dispositions  # noqa: E402

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "app", "ml", "prospective")


def main(name: str) -> None:
    path = os.path.join(DIR, name)
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    manifest = json.load(open(os.path.join(DIR, "MANIFEST.json")))
    entry = next((m for m in manifest if m["file"] == name), None)
    if entry is None or entry["sha256"] != digest:
        raise SystemExit(f"REFUSING: {name} does not match its recorded hash -- it was modified or never registered.")

    snap = json.load(open(path, encoding="utf-8"))
    result = evaluate(snap["rows"], current_dispositions(), list(snap["rows"][0]["flags"].keys()))
    result.update(snapshot=name, snapshot_created_at=snap["created_at"], snapshot_sha256=digest,
                  evaluated_at=datetime.now(timezone.utc).isoformat(), thresholds=snap["thresholds"],
                  hypothesis=snap["hypothesis"])
    out = os.path.join(DIR, f"evaluation_{name.replace('.json', '')}_{datetime.now(timezone.utc):%Y%m%d}.json")
    with open(out, "w") as f:
        json.dump(result, f, indent=1)

    print(f"{result['n_resolved']} of {result['n_in_snapshot']} resolved "
          f"({result['n_still_unresolved']} still unresolved, {result['n_withdrawn_excluded']} withdrawn/excluded)")
    p = result["per_flag"]["any_core_flag"]
    print(f"core flag: {p['n_flagged']} flagged ({p['fp_among_flagged']} FP), {p['n_clean']} clean ({p['fp_among_clean']} FP)")
    print(result["verdict"])
    print(f"Wrote {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: prospective_evaluate.py <snapshot file name in app/ml/prospective/>")
    main(sys.argv[1])
