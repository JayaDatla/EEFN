"""
Does the Kepler-trained light-curve vetter transfer to TESS?

Takes a random, class-balanced sample of TOIs whose TFOP disposition is already known
(CP/KP = planet, FP/FA = not a planet), downloads each one's REAL SPOC 2-minute TESS
light curve, runs the production vetter on it, and compares P(Planet Transit) with the
human label. Results are cached per TOI in tess_transfer_cache.json so an interrupted
run resumes where it stopped (each target is a real MAST download).

Caveats that are part of the result, not footnotes (also written into the report):
* TFOP dispositions were assigned by humans who looked at these same TESS light curves
  (and Gaia, and centroids), so agreement shows the model reproduces human vetting from
  the light curve -- not that it independently finds planets.
* Kepler -> TESS is a domain shift (different noise, far fewer transits per target), which
  is exactly what this measures.

    python validation/scripts/tess_transfer_check.py --n-per-class 30
"""
import argparse
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)

from app.ml.lightcurve_vetter import fetch_tess_lightcurve, lightcurve_vetter  # noqa: E402
from app.pipeline.errors import TransientCatalogError  # noqa: E402
from app.pipeline.mast_centroid import fetch_transit_epoch  # noqa: E402

DATA = os.path.join(REPO, "validation", "data", "validation_dataset.csv")
CACHE = os.path.join(BACKEND, "validation", "data", "tess_transfer_cache.json")
REPORT = os.path.join(BACKEND, "app", "ml", "tess_transfer_report.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-per-class", type=int, default=30)
    ap.add_argument("--max-attempts", type=int, default=400, help="stop after this many targets tried")
    args = ap.parse_args()

    df = pd.read_csv(DATA)
    df = df[df.tfopwg_disp.isin(["CP", "KP", "FP", "FA"])].copy()
    df["planet"] = df.tfopwg_disp.isin(["CP", "KP"]).astype(int)
    df = df.sample(frac=1.0, random_state=0).reset_index(drop=True)   # fixed shuffle -> reproducible sample

    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    done = {0: 0, 1: 0}
    for rec in cache.values():
        if rec.get("status") == "vetted":
            done[rec["planet"]] += 1
    attempts = 0

    for _, r in df.iterrows():
        key = str(int(r.tid))
        if key in cache:
            continue
        if done[0] >= args.n_per_class and done[1] >= args.n_per_class:
            break
        if done[int(r.planet)] >= args.n_per_class:
            continue
        if attempts >= args.max_attempts:
            break
        attempts += 1
        rec = {"toi": float(r.toi), "disp": r.tfopwg_disp, "planet": int(r.planet)}
        try:
            # Filtered to this TOI: a star can host several planets with different epochs/periods.
            epoch = fetch_transit_epoch(int(r.tid), toi_id=float(r.toi))
            lc = fetch_tess_lightcurve(int(r.tid), max_sectors=2) if epoch else None
        except TransientCatalogError as e:
            # Archive/MAST trouble says nothing about this target: skip WITHOUT caching it, so a
            # re-run tries again instead of recording a false "no_lightcurve".
            print(f"TIC {int(r.tid)} transient failure, not cached: {e}", flush=True)
            continue
        if not epoch:
            rec["status"] = "no_epoch"
        elif lc is None:
            rec["status"] = "no_lightcurve"
        else:
            t, f, sectors = lc
            stellar = {"teff": r.st_teff, "rstar": r.st_rad, "depth_ppm": r.pl_trandep,
                       "j_mag": r.Jmag, "k_mag": r.Kmag, "g_mag": r.PS_gmag, "r_mag": r.PS_rmag}
            out = lightcurve_vetter.vet(t, f, float(epoch["pl_orbper"] or r.pl_orbper),
                                        float(epoch["pl_tranmid"]) - 2457000.0,
                                        float(epoch["pl_trandurh"] or r.pl_trandurh), stellar)
            if out.get("model_status") != "trained":
                rec["status"] = "unusable"
            else:
                rec.update(status="vetted", sectors=sectors, classification=out["classification"],
                           best_class=out["best_class"], snr=out["features"].get("snr"))
                done[int(r.planet)] += 1
        cache[key] = rec
        json.dump(cache, open(CACHE, "w"))
        print(f"TIC {key} {r.tfopwg_disp:2s} -> {rec['status']:14s} {rec.get('best_class','')}  "
              f"[vetted: planets {done[1]}, non-planets {done[0]}]", flush=True)

    vetted = [v for v in cache.values() if v.get("status") == "vetted"]
    if len(vetted) < 10:
        print("Too few vetted targets for a report yet; re-run to continue.")
        return
    from sklearn.metrics import roc_auc_score
    y = np.array([v["planet"] for v in vetted])
    p = np.array([v["classification"]["Planet Transit"] for v in vetted])
    pred = (p >= 0.5).astype(int)
    tp, fn = int(((pred == 1) & (y == 1)).sum()), int(((pred == 0) & (y == 1)).sum())
    tn, fp = int(((pred == 0) & (y == 0)).sum()), int(((pred == 1) & (y == 0)).sum())
    report = {
        "n_vetted": len(vetted), "n_planets": int(y.sum()), "n_non_planets": int((1 - y).sum()),
        "accuracy": float((pred == y).mean()),
        "roc_auc_planet_vs_not": float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else None,
        "planet_recall": tp / max(tp + fn, 1), "non_planet_recall": tn / max(tn + fp, 1),
        "confusion": {"planet_called_planet": tp, "planet_called_not": fn,
                      "non_planet_called_not": tn, "non_planet_called_planet": fp},
        "status_counts": pd.Series([v.get("status") for v in cache.values()]).value_counts().to_dict(),
        "caveats": [
            "TFOP dispositions were assigned by humans who inspected these same TESS light curves (plus Gaia and "
            "centroids): agreement measures reproduction of human vetting, not independent discovery.",
            "Kepler -> TESS domain shift (noise, number of transits per target) is exactly what this measures.",
            "Small sample; treat the accuracy as +/- several points.",
        ],
        "model_version": lightcurve_vetter.version,
    }
    json.dump(report, open(REPORT, "w"), indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
