"""
Stellar density diagnostics used to sanity-check a transit against the host star's
independently known properties. See UPGRADE_PLAN.md A.4/C.4: the previous
`density_transit` formula never used the orbital period and did not resolve to g/cm^3.
"""
import math
from typing import Optional

G_CGS = 6.674e-8  # cm^3 g^-1 s^-2
SOLAR_DENSITY_CGS = 1.408  # g/cm^3; converts (Msun / Rsun^3) to g/cm^3

# Typical fractional precision of Gaia DR3 FLAME stellar radii, used only as a fallback
# when a target has no per-star b_Rad/B_Rad bounds from the cross-match. This is a
# disclosed default applied when real per-target uncertainty is unavailable, not a
# silently-invented constant applied identically regardless of what's measurable.
DEFAULT_RADIUS_FRACTIONAL_ERROR = 0.08

# Combined floor for uncertainty sources this pipeline does not yet propagate per-target
# (Gaia FLAME stellar mass error, transit period/duration error -- the NASA TAP query in
# ingest.py does not currently fetch pl_orbpererr*/pl_trandurherr*). Keeps
# density_discrepancy_sigma from claiming more precision than actually exists. See
# LIMITATIONS.md.
UNMODELED_SYSTEMATIC_FRACTIONAL_FLOOR = 0.10


def radius_ratio_from_depth_ppm(depth_ppm: Optional[float]) -> Optional[float]:
    """k = Rp/R* from the transit depth, k ~= sqrt(depth). Ignores limb darkening (which makes
    the true k slightly larger than sqrt(depth) for a central transit), a few-percent effect on k
    and a further ~1% on the density it feeds."""
    if depth_ppm is None or depth_ppm <= 0:
        return None
    return math.sqrt(depth_ppm * 1e-6)


def compute_transit_density_cgs(
    period_days: Optional[float],
    duration_hours: Optional[float],
    radius_ratio: Optional[float] = None,
) -> Optional[float]:
    """
    Stellar density implied by the transit's own geometry (Seager & Mallen-Ornelas 2003).
    For a circular orbit and a CENTRAL transit (b = 0) the total duration satisfies
        sin(pi * T14 / P) = (1 + k) / (a/R*),        k = Rp/R*
    so   a/R* = (1 + k) / sin(pi * T14 / P)
         rho* = 3*pi / (G * P^2) * (a/R*)^3
    Returns g/cm^3, or None if period/duration aren't available.

    `radius_ratio` (k) matters: the ingress/egress add k to the chord, so ignoring it (k = 0)
    underestimates the density by the factor (1+k)^3 (true/estimated = 1.28 for TRAPPIST-1b,
    k = 0.085; 1.52 for a giant planet with k = 0.15), so it matters most for exactly the large
    planets that dominate false-positive lists. Earlier versions omitted it
    and attributed the whole TRAPPIST-1b offset to the impact parameter; the exact form below
    reproduces that star's density (74.6 g/cm^3) to ~2%. When k is not supplied it defaults to 0
    (the old, biased-low behaviour), so callers should pass it whenever a depth is known.

    Remaining, disclosed assumptions: b = 0 (a nonzero impact parameter shortens T14 and biases the
    density HIGH for a given duration -- the opposite direction to the omitted-k error), circular
    orbit, and k from sqrt(depth) ignoring limb darkening. Real density from a transit alone is
    degenerate with b and eccentricity (Seager & Mallen-Ornelas 2003), so this is a screening
    quantity, not a measurement.
    """
    if not period_days or not duration_hours or period_days <= 0 or duration_hours <= 0:
        return None
    k = radius_ratio if radius_ratio is not None and radius_ratio > 0 else 0.0
    phase_arg = math.pi * (duration_hours / 24.0) / period_days     # pi * T14 / P
    if phase_arg >= math.pi / 2.0:
        return None    # duration >= half the period: not a physically sensible transit
    a_over_rstar = (1.0 + k) / math.sin(phase_arg)
    period_sec = period_days * 86400.0
    return 3.0 * math.pi / (G_CGS * period_sec ** 2) * a_over_rstar ** 3


def compute_gaia_density_cgs(mass_solar: Optional[float], radius_solar: Optional[float]) -> Optional[float]:
    """Evolutionary-model stellar density from Gaia DR3 FLAME mass/radius, in g/cm^3."""
    if not mass_solar or not radius_solar or radius_solar <= 0:
        return None
    return (mass_solar / (radius_solar ** 3)) * SOLAR_DENSITY_CGS


def half_width_from_asymmetric_bounds(value: Optional[float], lower_bound: Optional[float],
                                       upper_bound: Optional[float]) -> Optional[float]:
    """
    Gaia DR3 FLAME-style catalogs publish asymmetric bounds (b_X, B_X) around a
    parameter rather than a symmetric +/- error. Returns the average of the two
    half-widths as a working 1-sigma-equivalent estimate, or None if bounds aren't
    available -- callers decide their own fallback (see
    DEFAULT_RADIUS_FRACTIONAL_ERROR below for the pattern used elsewhere in this file).
    """
    if value is None or lower_bound is None or upper_bound is None:
        return None
    return (abs(value - lower_bound) + abs(upper_bound - value)) / 2.0


def compute_density_discrepancy_sigma(
    density_transit: Optional[float],
    density_gaia: Optional[float],
    radius_solar: Optional[float],
    radius_err_lower: Optional[float],
    radius_err_upper: Optional[float],
) -> Optional[float]:
    """
    How many "sigma" apart the transit-derived and Gaia-evolutionary densities are.
    sigma is the propagated uncertainty on density_gaia from its dominant, actually
    per-target-measured term -- Gaia FLAME radius, entering as R^-3 -- combined in
    quadrature with a documented floor for the terms not yet propagated per-target
    (stellar mass error, transit timing error). This replaces a hardcoded,
    target-independent "/0.3" divisor with a value that varies with how well each star
    is actually characterized (UPGRADE_PLAN.md A.4/C.4).
    """
    if density_transit is None or density_gaia is None:
        return None

    rad_err = half_width_from_asymmetric_bounds(radius_solar, radius_err_lower, radius_err_upper)
    if radius_solar and rad_err is not None:
        frac_rad_err = rad_err / radius_solar
    else:
        frac_rad_err = DEFAULT_RADIUS_FRACTIONAL_ERROR

    frac_density_err_from_radius = 3.0 * frac_rad_err  # rho ~ R^-3
    total_frac_err = math.sqrt(frac_density_err_from_radius ** 2 + UNMODELED_SYSTEMATIC_FRACTIONAL_FLOOR ** 2)
    sigma_abs = max(density_gaia * total_frac_err, 1e-6)

    return abs(density_transit - density_gaia) / sigma_abs
