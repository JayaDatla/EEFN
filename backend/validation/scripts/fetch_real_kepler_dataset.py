"""
Real-data training set for DeepExoFusionNet's Global/Local light-curve branches.

LIMITATIONS.md #7 disclosed that the deep learning model was trained entirely on
synthetic light curves. This script builds a real, labeled alternative from Kepler's
cumulative KOI table (NASA Exoplanet Archive, same TAP service ingest.py already
uses) -- the same source Shallue & Vanderburg (2018) used for the original
"exoplanet deep learning" work, and the only source with real per-example
false-positive *reason* flags, not just a disposition.

Kepler's own vetting flags do not distinguish "stellar activity" from "instrumental
noise" (koi_fpflag_nt covers both, undifferentiated) -- no standard dataset does,
at scale. So this trains 3 real classes, not the model's original 4:
    0 = Planet Transit    (CONFIRMED, no FP flags)
    1 = Eclipsing Binary  (fpflag_ss=1 or fpflag_co=1: stellar eclipse / centroid
                           offset -- a real background/blended eclipsing signal)
    2 = Not Transit-Like  (fpflag_nt=1 only: real, but Kepler's own pipeline does
                           not further split this into activity vs. noise either)
CANDIDATE rows and ambiguous multi-flag / ephemeris-contamination-only rows are
excluded to keep the three label buckets clean.

Deliberately NOT run automatically or at full scale in one pass -- each star's full
stitched light curve takes ~30-90s to download (real network cost, not an artifact
of this script), so this is a manually-run, resumable fetch with disk caching, same
posture as run_real_centroid_subset.py for MAST TPFs.

Usage:
    python validation/scripts/fetch_real_kepler_dataset.py --per-class 8
    python validation/scripts/fetch_real_kepler_dataset.py --per-class 200  # full run

Real per-star raw light curves are cached under validation/data/kepler_lc_cache/
(re-running never re-downloads a star already cached). The processed, model-ready
dataset (global/local views + metadata + label) is written to
validation/data/real_kepler_training_set.npz for train_deep_learning.py to load
with no network access needed at train time.
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.ml.deep_learning_pipeline import dl_vetting_engine

NASA_TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data")
LC_CACHE_DIR = os.path.join(DATA_DIR, "kepler_lc_cache")
DATASET_PATH = os.path.join(DATA_DIR, "real_kepler_training_set.npz")
REPORT_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), "..", "app", "ml", "real_kepler_dataset_report.json")

FIELDS = (
    "kepid,ra,dec,koi_disposition,koi_fpflag_nt,koi_fpflag_ss,koi_fpflag_co,koi_fpflag_ec,"
    "koi_period,koi_duration,koi_time0bk,koi_depth,koi_steff,koi_srad,koi_slogg,koi_kepmag"
)

# (label, WHERE clause) -- see module docstring for the real-flag mapping rationale.
LABEL_QUERIES = [
    (0, "koi_disposition='CONFIRMED' AND koi_fpflag_nt=0 AND koi_fpflag_ss=0 AND koi_fpflag_co=0 AND koi_fpflag_ec=0"),
    (1, "koi_disposition='FALSE POSITIVE' AND (koi_fpflag_ss=1 OR koi_fpflag_co=1)"),
    (2, "koi_disposition='FALSE POSITIVE' AND koi_fpflag_nt=1 AND koi_fpflag_ss=0 AND koi_fpflag_co=0"),
]
LABEL_NAMES = {0: "Planet Transit", 1: "Eclipsing Binary", 2: "Not Transit-Like"}


def _get_with_retry(url: str, params: dict, attempts: int = 5, timeout: float = 30.0):
    """
    Retry with exponential backoff on transient network failures. A single
    unretried DNS blip ('Failed to resolve exoplanetarchive.ipac.caltech.edu')
    killed a ~40-minute unattended run of this script and discarded all of its
    processed work -- this is a long, network-bound job and must survive one bad
    lookup. Mirrors the retry posture ingest.py already uses for its own
    NASA TAP / CDS X-Match calls.
    """
    last_exc = None
    for attempt in range(attempts):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:  # network, DNS, HTTP 5xx
            last_exc = e
            if attempt == attempts - 1:
                break
            backoff = 2.0 ** attempt
            print(f"    request failed ({e.__class__.__name__}), retrying in {backoff:.0f}s "
                  f"[{attempt + 1}/{attempts}]")
            time.sleep(backoff)
    raise last_exc


def fetch_koi_rows(label: int, where: str, limit: int) -> list:
    query = f"SELECT TOP {limit} {FIELDS} FROM cumulative WHERE {where} AND koi_period IS NOT NULL AND koi_duration IS NOT NULL AND koi_time0bk IS NOT NULL"
    r = _get_with_retry(NASA_TAP_URL, {"query": query, "format": "json"})
    return r.json()


def fetch_real_lightcurve(kepid: int) -> dict | None:
    """Downloads and stitches all available real Kepler long-cadence quarters for
    this star, caching the raw (time, flux) arrays to disk so a re-run of this
    script (or a bigger --per-class pass later) never re-downloads a star it
    already has. Returns None (never fabricated) if no real data is available."""
    cache_path = os.path.join(LC_CACHE_DIR, f"{kepid}.npz")
    if os.path.exists(cache_path):
        d = np.load(cache_path)
        return {"time": d["time"], "flux": d["flux"]}

    import lightkurve as lk
    try:
        search = lk.search_lightcurve(f"KIC {kepid}", mission="Kepler", cadence="long", author="Kepler")
        if len(search) == 0:
            return None
        lcc = search.download_all()
        if lcc is None or len(lcc) == 0:
            return None
        lc = lcc.stitch()
        flux = np.asarray(lc["flux"].value, dtype=np.float64)
        time_arr = np.asarray(lc["time"].value, dtype=np.float64)
        valid = np.isfinite(flux) & np.isfinite(time_arr)
        flux, time_arr = flux[valid], time_arr[valid]
        if len(flux) < 50:
            return None
        os.makedirs(LC_CACHE_DIR, exist_ok=True)
        np.savez(cache_path, time=time_arr, flux=flux)
        return {"time": time_arr, "flux": flux}
    except Exception as e:
        print(f"    fetch failed for KIC {kepid}: {e}")
        return None


def build_metadata(row: dict) -> dict:
    """Real Kepler-native stellar parameters where the archive has them; every
    other optional field (RUWE, 2MASS/Pan-STARRS photometry, catalog-disagreement
    deltas) is genuinely not cross-matched here and stays absent -- build_metadata_vector
    marks it with a real presence=0 bit rather than substituting a fabricated value."""
    return {
        "st_teff": row.get("koi_steff"),
        "st_rad": row.get("koi_srad"),
        "trandep": row.get("koi_depth"),
    }


def save_dataset(data_list: list) -> None:
    """Writes the processed, model-ready dataset. Called both at each per-class
    checkpoint and at the end, so the two can never write different formats."""
    np.savez(
        DATASET_PATH,
        global_views=np.stack([d[0] for d in data_list]),
        local_views=np.stack([d[1] for d in data_list]),
        centroids=np.stack([d[2] for d in data_list]),
        labels=np.array([d[4] for d in data_list], dtype=np.int64),
    )
    # Raw metadata dicts (may contain None) can't go in an npz array -- saved
    # alongside as JSON, same row order as the arrays above.
    with open(DATASET_PATH.replace(".npz", "_metadata.json"), "w") as f:
        json.dump([d[3] for d in data_list], f)


def run(per_class: int, sleep_between: float = 0.5):
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LC_CACHE_DIR, exist_ok=True)

    data_list = []
    per_label_counts = {}
    per_label_attempted = {}
    started = time.time()

    for label, where in LABEL_QUERIES:
        print(f"\n=== Label {label} ({LABEL_NAMES[label]}) ===")
        rows = fetch_koi_rows(label, where, per_class)
        print(f"  {len(rows)} real KOI rows matched (requested up to {per_class}).")
        per_label_attempted[label] = len(rows)
        n_ok = 0
        for i, row in enumerate(rows):
            kepid = row["kepid"]
            print(f"  [{i+1}/{len(rows)}] KIC {kepid} ...", end=" ", flush=True)
            lc = fetch_real_lightcurve(kepid)
            if lc is None:
                print("no real light curve available.")
                continue

            period = float(row["koi_period"])
            duration_hours = float(row["koi_duration"])
            t0 = float(row["koi_time0bk"])

            global_v, local_v = dl_vetting_engine.preprocess_lightcurve(
                time=lc["time"], flux=lc["flux"], period=period, duration_hours=duration_hours, t0=t0,
            )
            # No real TPF centroid ingestion for Kepler in this pass -- honestly
            # absent (zeroed + presence=0), the same convention build_centroid_matrix
            # already uses for any candidate with no real centroid measurement.
            centroid_matrix = np.zeros((3, 201), dtype=np.float32)
            # Raw fields, NOT a pre-built build_metadata_vector() output -- saved this
            # way so train_deep_learning.py can apply the same per-field dropout
            # augmentation (on the raw dict) that the synthetic path always used,
            # instead of needing to know build_metadata_vector's internal index layout.
            meta = build_metadata(row)

            data_list.append((
                (global_v - 1.0).astype(np.float32),
                (local_v - 1.0).astype(np.float32),
                centroid_matrix,
                meta,
                label,
            ))
            n_ok += 1
            print(f"ok ({len(lc['time'])} real cadences).")
            time.sleep(sleep_between)

        per_label_counts[label] = n_ok
        print(f"  -> {n_ok}/{len(rows)} real light curves usable for label {label}.")
        # Checkpoint after every class: a crash in a later class must not discard
        # the (network-expensive) work already done for earlier ones.
        if data_list:
            save_dataset(data_list)
            print(f"  [checkpoint] {len(data_list)} samples saved so far.")

    if not data_list:
        raise RuntimeError("No real light curves were fetched -- nothing to save.")

    save_dataset(data_list)
    elapsed = time.time() - started

    report = {
        "generated_at_unix": time.time(),
        "elapsed_seconds": round(elapsed, 1),
        "per_class_requested": per_class,
        "per_class_attempted": per_label_attempted,
        "per_class_usable": per_label_counts,
        "total_usable_samples": len(data_list),
        "label_names": LABEL_NAMES,
        "source": "NASA Exoplanet Archive cumulative KOI table + real Kepler long-cadence light curves via lightkurve/MAST",
        "note": (
            "Real light curves and real disposition/false-positive-flag labels throughout. "
            "No real TPF centroid for Kepler stars in this pass -- centroid branch is honestly "
            "zeroed+presence=0 for every sample here, same convention as any TESS candidate "
            "with no real centroid measurement. Metadata vector uses real koi_steff/koi_srad/"
            "koi_depth only; no 2MASS/Pan-STARRS/RUWE cross-match attempted for these stars."
        ),
    }
    os.makedirs(os.path.dirname(os.path.abspath(REPORT_PATH)), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nSaved {len(data_list)} real samples to {DATASET_PATH}")
    print(f"Wrote report to {REPORT_PATH}")
    print(f"Elapsed: {elapsed:.1f}s")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-class", type=int, default=8)
    parser.add_argument("--sleep", type=float, default=0.5, help="seconds between star downloads (politeness)")
    args = parser.parse_args()
    run(args.per_class, args.sleep)
