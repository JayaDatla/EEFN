"""
Gaia-derived planet radius and its propagated uncertainty (UPGRADE_PLAN.md E.3): "A
derived radius should read 5.46 ± 0.31 R⊕, not a bare point estimate, everywhere it's
shown." The point-estimate formula (Rp = R* * sqrt(depth) * 109.2, i.e. transit depth
implies a radius ratio, scaled to Earth radii via the solar-to-Earth radius ratio)
was previously computed independently in both `ingest.py` and `predict.py` with no
shared uncertainty term -- both now call this module so a future formula change can't
make the two silently disagree.
"""
import math
from typing import Optional

from app.science.density import half_width_from_asymmetric_bounds

SOLAR_TO_EARTH_RADIUS_RATIO = 109.2

# Applied when a per-target transit-depth error isn't available (NASA TAP occasionally
# omits pl_trandeperr1/2 for a given TOI even though the depth itself is present).
# This is a disclosed default, not a silently-invented one -- see LIMITATIONS.md.
DEFAULT_TRANDEP_FRACTIONAL_ERROR = 0.10


def compute_derived_planet_radius_earth(radius_solar: Optional[float],
                                         transit_depth_ppm: Optional[float]) -> Optional[float]:
    """Rp [R_Earth] implied by the star's radius and the observed transit depth,
    independent of the catalog's own pl_rade value -- this is what predict.py's
    is_unphysical_rp check and ingest.py's derived_rp_diff compare pl_rade against."""
    if not radius_solar or not transit_depth_ppm or transit_depth_ppm < 0:
        return None
    return radius_solar * math.sqrt(transit_depth_ppm * 1e-6) * SOLAR_TO_EARTH_RADIUS_RATIO


def compute_derived_planet_radius_uncertainty(
    radius_solar: Optional[float],
    radius_err_lower: Optional[float],
    radius_err_upper: Optional[float],
    transit_depth_ppm: Optional[float],
    transit_depth_err: Optional[float],
) -> Optional[float]:
    """
    Propagates uncertainty on the derived radius above via standard fractional-
    quadrature error propagation for Rp = R* * depth^0.5 * const:
        (sigma_Rp / Rp)^2 = (sigma_R* / R*)^2 + (0.5 * sigma_depth / depth)^2
    `radius_err_lower`/`radius_err_upper` are Gaia FLAME-style asymmetric bounds
    (b_Rad/B_Rad), not a symmetric +/- error -- see
    `density.half_width_from_asymmetric_bounds`. `transit_depth_err` is expected as an
    already-symmetrized absolute error (e.g. mean of |pl_trandeperr1| and
    |pl_trandeperr2|, which NASA TAP publishes as equal-magnitude +/- values); falls
    back to DEFAULT_TRANDEP_FRACTIONAL_ERROR when unavailable, same disclosed-default
    pattern as density.py's DEFAULT_RADIUS_FRACTIONAL_ERROR.
    """
    rp = compute_derived_planet_radius_earth(radius_solar, transit_depth_ppm)
    if rp is None:
        return None

    rad_err = half_width_from_asymmetric_bounds(radius_solar, radius_err_lower, radius_err_upper)
    if rad_err is None or not radius_solar:
        return None  # no real stellar-radius uncertainty available -- don't fabricate one
    frac_rad_err = rad_err / radius_solar

    if transit_depth_err is not None and transit_depth_ppm:
        frac_depth_err = abs(transit_depth_err) / transit_depth_ppm
    else:
        frac_depth_err = DEFAULT_TRANDEP_FRACTIONAL_ERROR

    frac_rp_err = math.sqrt(frac_rad_err ** 2 + (0.5 * frac_depth_err) ** 2)
    return rp * frac_rp_err
