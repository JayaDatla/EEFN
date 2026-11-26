"""
Observational novelty: how under-represented a candidate's properties are among confirmed transiting planets.

This is a SEPARATE axis from the model's planet probability and from the catalog checks; nothing here changes
a grade, a check or a sort unless the user chooses it. It follows a reviewer's suggestion (B. Escola-Rodrigo,
personal communication): use the NASA Exoplanet Archive PSCompPars table, transform and normalise the
properties, estimate their joint density, and measure how rare a candidate's combination is. A giant planet
is not unusual by itself, but a giant planet around a very low-mass star is.

What it is and is not:
* It measures observational novelty (rarity in the OBSERVED sample), not intrinsic rarity. The confirmed
  population is shaped by detection ability, follow-up priority and validation, so a region can be empty
  because planets there are hard to find, not because they are rare.
* It assumes the candidate's inferred properties are reliable. It uses the TOI table's planet radius and the
  Gaia stellar mass; it is None (not zero) when either is missing, and None when the radius is above the
  22 R_Earth physical limit, so a blended eclipsing binary does not look "interesting".
* It says nothing about whether the candidate is a planet. A false positive can have an unusual radius.

Method: Gaussian KDE in standardised (log10 radius, log10 period, log10 stellar mass), fitted to the reference
planets. The score is the share of reference planets that sit in a DENSER region than the candidate:
0 = as common as the most common planets, 1 = rarer than every reference planet (outside the observed range;
log10_density then separates them).
"""
import json
import math
import os
from functools import lru_cache
from typing import Any, Dict, Optional

import numpy as np

REFERENCE_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml", "interest_reference.csv")
MAX_PHYSICAL_RADIUS_EARTH = 22.0


@lru_cache(maxsize=1)
def _model() -> Optional[Dict[str, Any]]:
    """KDE and the reference densities, or None when the reference file has not been built."""
    if not os.path.exists(REFERENCE_CSV):
        return None
    from scipy.stats import gaussian_kde
    import pandas as pd
    ref = pd.read_csv(REFERENCE_CSV)
    X = np.log10(ref[["pl_rade", "pl_orbper", "st_mass"]].to_numpy(dtype=float))
    mu, sd = X.mean(axis=0), X.std(axis=0)
    Z = ((X - mu) / sd).T
    kde = gaussian_kde(Z)
    ref_density = kde(Z)
    prov = {}
    try:
        with open(REFERENCE_CSV.replace(".csv", ".json")) as f:
            prov = json.load(f)
    except (OSError, ValueError):
        pass
    return {"kde": kde, "mu": mu, "sd": sd, "ref_density": np.sort(ref_density), "n": int(len(ref)), "provenance": prov}


def novelty(radius_earth: Optional[float], period_days: Optional[float], star_mass_solar: Optional[float]) -> Dict[str, Any]:
    """Novelty in [0, 1], or None with a reason. Pure apart from the cached reference."""
    m = _model()
    if m is None:
        return {"novelty": None, "reason": "reference table not built (validation/scripts/build_interest_reference.py)"}
    vals = (radius_earth, period_days, star_mass_solar)
    if any(v is None or not math.isfinite(v) or v <= 0 for v in vals):
        return {"novelty": None, "reason": "needs a planet radius, an orbital period and a Gaia stellar mass"}
    if radius_earth > MAX_PHYSICAL_RADIUS_EARTH:
        return {"novelty": None, "reason": f"radius above {MAX_PHYSICAL_RADIUS_EARTH:g} R_Earth is not a physical planet size"}
    z = ((np.log10(np.array(vals, dtype=float)) - m["mu"]) / m["sd"]).reshape(3, 1)
    density = float(m["kde"](z)[0])
    # share of reference planets in a denser region than this candidate
    denser = 1.0 - np.searchsorted(m["ref_density"], density, side="left") / len(m["ref_density"])
    # log10_density breaks ties among candidates at 1.0 (rarer than every reference planet); lower = rarer
    return {"novelty": round(float(denser), 3), "log10_density": round(math.log10(max(density, 1e-300)), 3),
            "reason": None, "n_reference": m["n"]}


def candidate_novelty(cand: Any, host: Any) -> Dict[str, Any]:
    return novelty(getattr(cand, "rade", None), getattr(cand, "orbper", None), getattr(host, "mass", None))


def describe() -> Dict[str, Any]:
    m = _model()
    return {"available": m is not None, "n_reference": m["n"] if m else 0, "provenance": m["provenance"] if m else {},
            "meaning": "Share of confirmed transiting planets in a denser region of (radius, period, star mass). "
                       "Observational novelty, not intrinsic rarity; says nothing about whether it is a planet."}
