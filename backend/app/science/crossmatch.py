"""
Cross-match quality: did the Gaia source we matched to this TOI really come from the same star?

A wrong-star match (a neighbour inside the 5 arcsec radius, or a high-proper-motion star that moved
out of it) silently poisons every downstream number: RUWE, parallax, radius, Teff, distance and the
disagreement features are then properties of a different star, and would read as a convincing
"disagreement" or a convincing "agreement" with equal ease.

TIC-8's T magnitude is derived from Gaia photometry, so T - G is a tight function of Gaia colour.
Fitted on the project's 2,660 TOIs with all four magnitudes (iteratively sigma-clipped cubic in
BP-RP), the robust scatter about that relation is only 0.011 mag. A residual above 0.15 mag is >13
sigma: it means the matched Gaia star's photometry disagrees with the TOI's own. This is a screening
test, not a proof: a real residual can also come from a wrong TIC magnitude or heavy variability,
and a wrong-star match between two stars of the same colour and brightness would pass.
"""
import math
from typing import Any, Dict, Optional

# T - G = polyval(coeffs, BP - RP), highest power first. Fitted 2026-10-13 on validation_dataset.csv
# (n=2660, colour range -0.38 to 6.78, robust sigma 0.011 mag).
TG_COLOUR_COEFFS = (0.0006, 0.0423, -0.5903, 0.0244)
TG_ROBUST_SIGMA_MAG = 0.011
RESIDUAL_THRESHOLD_MAG = 0.15
MATCH_SEPARATION_THRESHOLD_ARCSEC = 3.0     # the cross-match radius is 5 arcsec; most true matches are << 1 arcsec
FITTED_COLOUR_RANGE = (-0.4, 6.8)


def expected_t_minus_g(bp_rp: float) -> float:
    a, b, c, d = TG_COLOUR_COEFFS
    return ((a * bp_rp + b) * bp_rp + c) * bp_rp + d


def tmag_gmag_residual(tmag: Optional[float], gmag: Optional[float], bp_rp: Optional[float]) -> Optional[float]:
    """Observed (T - G) minus the colour-predicted value, in magnitudes. None if any input is missing
    or the colour lies outside the range the relation was fitted on."""
    if tmag is None or gmag is None or bp_rp is None:
        return None
    if not (FITTED_COLOUR_RANGE[0] <= bp_rp <= FITTED_COLOUR_RANGE[1]):
        return None
    return (tmag - gmag) - expected_t_minus_g(bp_rp)


def crossmatch_quality(host: Any) -> Dict[str, Optional[float]]:
    """Stored match diagnostics for a host row. `suspect` is None until the host has been (re-)ingested
    with the match inputs; it is never False merely because those inputs are absent. Decision order:
    photometric residual if computable, else match separation, else unknown."""
    resid = tmag_gmag_residual(getattr(host, "toi_tmag", None), getattr(host, "gaia_g_mag", None),
                               getattr(host, "gaia_bp_rp", None))
    sep = getattr(host, "gaia_match_sep_arcsec", None)
    # The photometry is the stronger evidence. A 3-5 arcsec separation with consistent T-G is almost
    # always the right star with an imperfect TOI position (on the project's 506 matched hosts, flagging
    # on separation alone fired for ~5% of matches whose photometry agreed to ~0.01 mag), so separation is
    # only used when the photometric test cannot be run.
    if resid is not None:
        suspect = abs(resid) > RESIDUAL_THRESHOLD_MAG
    elif sep is not None:
        suspect = sep > MATCH_SEPARATION_THRESHOLD_ARCSEC
    else:
        suspect = None
    return {
        "tmag_gmag_residual_mag": None if resid is None else round(resid, 3),
        "residual_sigma": None if resid is None else round(resid / TG_ROBUST_SIGMA_MAG, 1),
        "match_separation_arcsec": sep,
        "suspect": suspect,
    }
