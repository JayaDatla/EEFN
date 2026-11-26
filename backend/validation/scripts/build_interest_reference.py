"""
Build the reference table for the observational-novelty score from a PSCompPars download.

Download (NASA Exoplanet Archive TAP, confirmed transiting planets; run once, by hand):
    curl -G "https://exoplanetarchive.ipac.caltech.edu/TAP/sync" \
      --data-urlencode "query=select pl_name,hostname,pl_rade,pl_orbper,pl_bmasse,pl_eqt,st_teff,st_rad,st_mass,sy_dist,disc_year from pscomppars where discoverymethod='Transit'" \
      --data-urlencode "format=csv" -o backend/validation/data/pscomppars_transit.csv

Then:  python validation/scripts/build_interest_reference.py
Writes backend/app/ml/interest_reference.csv (radius, period, star mass; complete rows only) and a
provenance sidecar, so the score is reproducible and the production code needs no network access.
"""
import json
import os
from datetime import datetime, timezone

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(BACKEND, "validation", "data", "pscomppars_transit.csv")
OUT = os.path.join(BACKEND, "app", "ml", "interest_reference.csv")


def main():
    raw = pd.read_csv(RAW)
    cols = ["pl_name", "pl_rade", "pl_orbper", "st_mass"]
    ref = raw[cols].dropna()
    ref = ref[(ref.pl_rade > 0) & (ref.pl_orbper > 0) & (ref.st_mass > 0)]
    ref.to_csv(OUT, index=False)
    with open(OUT.replace(".csv", ".json"), "w") as f:
        json.dump({
            "source": "NASA Exoplanet Archive, table pscomppars, discoverymethod = Transit (TAP sync, CSV)",
            "built_at": datetime.now(timezone.utc).isoformat(),
            "n_downloaded": int(len(raw)), "n_reference": int(len(ref)),
            "columns": {"pl_rade": "Earth radii", "pl_orbper": "days", "st_mass": "solar masses"},
            "note": "Observed, detection-biased population. Used for observational novelty, not intrinsic rarity.",
        }, f, indent=2)
    print(f"{len(raw)} downloaded -> {len(ref)} complete rows -> {OUT}")


if __name__ == "__main__":
    main()
