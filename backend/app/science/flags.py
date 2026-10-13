"""
Catalog-hygiene flags for a TOI, with FIXED thresholds.

These are the flags the prospective evaluation (docs/prospective_evaluation.md) pre-registers: the
thresholds below are written into every snapshot, and changing them means starting a new snapshot,
not re-scoring an old one. Each flag is a simple, explainable test with a documented source; a flag
is None (not False) when its inputs are missing, so "could not check" never reads as "checked, clean".

Provenance of the thresholds (see reports/Cross catalog exoplanet vetting review.md):
* RUWE > 1.4 is the long-standing single-star cut (Lindegren+2021, DR2/DR3-era convention); 1.25 is
  the stricter DR3-calibrated cut. RUWE has well-known blind spots (it misses companions closer than
  ~0.1 arcsec at short periods and wide pairs), so a clean RUWE means "no astrometric evidence of a
  companion", NOT "no companion".
* 22 R_Earth: a transiting planet this large is not physically plausible (> ~2 Jupiter radii).
* TIC-vs-Gaia Teff scatter is ~122 K (Stassun+2019); 400 K is > 3 sigma of that scatter.
* The TIC radius is itself computed from Gaia DR2, so a TOI-vs-Gaia radius difference is mostly method
  noise; 30% is chosen to flag only gross disagreements.
"""
import math
from typing import Any, Dict, Optional

from app.science.density import compute_gaia_density_cgs, compute_transit_density_cgs, radius_ratio_from_depth_ppm
from app.science.radius import compute_derived_planet_radius_earth

THRESHOLDS = {
    "ruwe_possible_binary": 1.25,
    "ruwe_likely_binary": 1.4,
    "unphysical_planet_radius_earth": 22.0,
    # ln(rho_transit / rho_gaia): central 95% of the 128 CONFIRMED planets (CP/KP) with usable values in this
    # project's database, so the flag has a ~5% false-alarm rate on confirmed planets by construction. The
    # asymmetry is physical: the b=0 transit density is biased HIGH by (1-b^2)^-3/2 for any real impact
    # parameter (and eccentricity), so confirmed planets sit at a median ln-ratio of +0.58. A first version
    # used a 3-sigma cut with a ~26% error bar and fired on 52% of confirmed planets -- useless. Calibrated
    # on confirmed planets only (no test-set outcomes); recorded here so it cannot drift silently.
    "density_log_ratio_low": -0.45,
    "density_log_ratio_high": 2.72,
    "teff_difference_kelvin": 400.0,
    "radius_difference_fraction": 0.30,
    "evidence_score_low": 0.30,
}

# The flags that are about the host-star CATALOG record (no light curve, no model): the ones the
# "catalog hygiene" product claim rests on. Pre-registered as the primary hypothesis.
CORE_FLAGS = ["ruwe_likely_binary", "unphysical_radius", "density_inconsistent", "teff_outlier", "radius_outlier"]


def _gt(value: Optional[float], threshold: float) -> Optional[bool]:
    return None if value is None else bool(value > threshold)


def compute_flags(cand: Any, host: Any, prediction: Any = None) -> Dict[str, Optional[bool]]:
    """Flags from a candidate row, its host row, and (optionally) its stored prediction. Pure: reads
    attributes only, so it works on ORM rows or any object with the same fields."""
    ruwe = getattr(host, "ruwe", None)

    derived_rp = compute_derived_planet_radius_earth(getattr(host, "rad", None), getattr(cand, "trandep", None))

    density_transit = compute_transit_density_cgs(
        getattr(cand, "orbper", None), getattr(cand, "trandurh", None),
        radius_ratio=radius_ratio_from_depth_ppm(getattr(cand, "trandep", None)))
    density_gaia = compute_gaia_density_cgs(getattr(host, "mass", None), getattr(host, "rad", None))
    log_ratio = math.log(density_transit / density_gaia) if density_transit and density_gaia else None

    toi_teff, gaia_teff = getattr(host, "toi_teff", None), getattr(host, "teff", None)
    toi_rad, gaia_rad = getattr(host, "toi_rad", None), getattr(host, "rad", None)
    teff_diff = abs(toi_teff - gaia_teff) if toi_teff is not None and gaia_teff is not None else None
    rad_diff_frac = (abs(toi_rad - gaia_rad) / gaia_rad) if toi_rad is not None and gaia_rad else None

    score = getattr(prediction, "evidence_consistency_score", None) if prediction is not None else None
    return {
        "ruwe_possible_binary": _gt(ruwe, THRESHOLDS["ruwe_possible_binary"]),
        "ruwe_likely_binary": _gt(ruwe, THRESHOLDS["ruwe_likely_binary"]),
        "unphysical_radius": _gt(derived_rp, THRESHOLDS["unphysical_planet_radius_earth"]),
        "density_inconsistent": (None if log_ratio is None else bool(
            log_ratio < THRESHOLDS["density_log_ratio_low"] or log_ratio > THRESHOLDS["density_log_ratio_high"])),
        "teff_outlier": _gt(teff_diff, THRESHOLDS["teff_difference_kelvin"]),
        "radius_outlier": _gt(rad_diff_frac, THRESHOLDS["radius_difference_fraction"]),
        "gaia_parameters_missing": None if host is None else bool(gaia_teff is None and gaia_rad is None),
        "evidence_score_low": None if score is None else bool(score < THRESHOLDS["evidence_score_low"]),
    }


def any_core_flag(flags: Dict[str, Optional[bool]]) -> Optional[bool]:
    """True if any core flag fired; False only if every core flag was checkable and clean; None if
    nothing could be checked."""
    vals = [flags.get(k) for k in CORE_FLAGS]
    if any(v is True for v in vals):
        return True
    return False if any(v is False for v in vals) else None
