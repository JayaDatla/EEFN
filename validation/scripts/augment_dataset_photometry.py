"""
Adds real 2MASS (J/H/K) and Pan-STARRS DR1 (g/r/i/z/y) photometry to
validation/data/validation_dataset.csv via the same CDS X-Match helper the live
ingestion pipeline uses (app.pipeline.ingest.xmatch_catalog), so the Random Forest can
be trained on the catalogs EEFN actually ingests (LIMITATIONS.md 1.5 "Still not done").

Idempotent: re-running refreshes the photometry columns in place. Stars with no match
keep NaN -- the RF's imputer / the DL's presence bits handle that; nothing is filled in.

    python validation/scripts/augment_dataset_photometry.py
"""
import os
import sys
import time

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(REPO_ROOT, "backend"))

from app.pipeline import catalog_registry as catalog
from app.pipeline.ingest import xmatch_catalog

DATA_PATH = os.path.join(REPO_ROOT, "validation", "data", "validation_dataset.csv")

TWO_MASS_COLS = {"Jmag": "Jmag", "Hmag": "Hmag", "Kmag": "Kmag"}
PS1_COLS = {"gmag": "PS_gmag", "rmag": "PS_rmag", "imag": "PS_imag", "zmag": "PS_zmag", "ymag": "PS_ymag"}


class _Limiter:
    def acquire(self):
        time.sleep(0.5)


def main():
    df = pd.read_csv(DATA_PATH)
    df = df.drop(columns=[c for c in list(TWO_MASS_COLS.values()) + list(PS1_COLS.values()) if c in df.columns])
    csv = df[["toi", "ra", "dec"]].to_csv(index=False)

    limiter = _Limiter()
    for spec, mapping in ((catalog.TWO_MASS, TWO_MASS_COLS), (catalog.PAN_STARRS, PS1_COLS)):
        cols = ["toi"] + list(mapping.keys())
        matched = xmatch_catalog(spec, csv, limiter, cols)
        if matched.empty:
            raise SystemExit(f"{spec.name} cross-match returned nothing -- refusing to write a dataset without it.")
        matched = matched.rename(columns=mapping)
        matched["toi"] = matched["toi"].astype(df["toi"].dtype)
        df = df.merge(matched, on="toi", how="left")
        print(f"{spec.name}: matched {matched[list(mapping.values())[0]].notna().sum()}/{len(df)} rows")

    df.to_csv(DATA_PATH, index=False)
    print(f"Wrote {DATA_PATH} with {df.shape[1]} columns.")


if __name__ == "__main__":
    main()
