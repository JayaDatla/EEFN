"""
Tiered inference reporting (UPGRADE_PLAN.md F.1): every API response/UI surface must
show which tier of evidence actually backs a candidate's score, and how many of the
7 catalogs the v2 architecture is designed for actually contributed to it -- "a number
silently computed from zero-filled missing catalogs is worse than an honestly
incomplete one."

| Tier | Requires | Component |
|---|---|---|
| 0 | any data at all | Rule engine (alert_engine.py) |
| 1 | NASA/TOI + Gaia (source + astroparams) | RF tabular model |
| 2 | Tier 1 + real TESS light curve | Global+Local CNN branches |
| 3 | Tier 2 + TPF centroid + 2MASS/Pan-STARRS/spectroscopy | Full 4-branch net |

Tier 2 and Tier 3 are architecturally defined here but cannot be reached by any
candidate in this codebase today: no real MAST light curve or TPF centroid ingestion
exists yet (UPGRADE_PLAN.md F.6) -- `transit_pipeline.py` only ever simulates a light
curve. This module reports that honestly (every candidate currently tops out at Tier
1, or Tier 0 if even Gaia is unmatched) rather than pretending coverage that isn't
real.

IMPORTANT, learned the hard way while building this: `ExoplanetCandidate.centroid_shift_max`
and `HostStar.teff_spec`/`fe_h` can be non-null in this database for a reason that has
nothing to do with real ingestion -- `backend/seed_db.py` fabricates demo values for
all three (random centroid shifts, `gaia_teff + random jitter` for teff_spec, etc.)
and no real F.6/F.7 ingestion path exists to have populated them instead. Checking
"is this field non-null" for centroid/spectroscopy availability would therefore
launder seed-demo fabrication into an availability claim -- exactly the kind of
dishonesty this feature exists to prevent. So, unlike 2MASS/Pan-STARRS/Gaia (which
*are* real via live ingestion and are safely read from their DB fields directly),
centroid and spectroscopy availability are represented as explicit caller-supplied
flags, always False by default, the same pattern as `has_real_light_curve`.
"""
from dataclasses import dataclass
from typing import List, Optional

from app.db.models import ExoplanetCandidate, HostStar

CATALOG_NAMES = [
    "NASA Exoplanet Archive/TOI",
    "Gaia DR3 Source",
    "Gaia DR3 Astrophysical Parameters",
    "2MASS Photometry",
    "Pan-STARRS Photometry",
    "Spectroscopy (APOGEE/GALAH/LAMOST)",
    "MAST TESS FITS (light curve + centroid)",
]


@dataclass
class TierResult:
    tier: int
    tier_name: str
    catalogs_available: List[str]
    catalogs_missing: List[str]
    catalogs_total: int
    coverage_fraction: float


def compute_catalog_availability(candidate: ExoplanetCandidate, host: Optional[HostStar],
                                  has_real_spectroscopy: bool = False,
                                  has_real_centroid: bool = False) -> List[str]:
    """
    Which of the 7 catalogs actually contributed real, non-null data for this
    specific candidate -- not which catalogs the pipeline attempted to query, and
    never inferred from a field that `seed_db.py` can also populate with fabricated
    demo data (see module docstring for why centroid/spectroscopy are explicit flags,
    not field-presence checks).
    """
    available = ["NASA Exoplanet Archive/TOI"]  # true by definition: the candidate exists
    if host and (host.parallax is not None or host.ruwe is not None):
        available.append("Gaia DR3 Source")
    if host and (host.teff is not None or host.rad is not None):
        available.append("Gaia DR3 Astrophysical Parameters")
    if host and host.j_mag is not None:
        available.append("2MASS Photometry")
    if host and host.g_mag is not None:
        available.append("Pan-STARRS Photometry")
    if has_real_spectroscopy:
        available.append("Spectroscopy (APOGEE/GALAH/LAMOST)")
    if has_real_centroid:
        available.append("MAST TESS FITS (light curve + centroid)")
    return available


def compute_model_tier(candidate: ExoplanetCandidate, host: Optional[HostStar],
                        has_real_light_curve: bool = False,
                        has_real_centroid: bool = False,
                        has_real_spectroscopy: bool = False) -> TierResult:
    """
    `has_real_light_curve`/`has_real_centroid`/`has_real_spectroscopy` must be passed
    explicitly by the caller rather than inferred -- no code path in this repo sets
    any of them True today, since real MAST light curve/centroid ingestion (F.6) and
    real spectroscopy ingestion (F.7) don't exist yet. The honest default is False for
    all three, not a placeholder to quietly forget about once F.6/F.7 land.
    """
    available = compute_catalog_availability(candidate, host, has_real_spectroscopy, has_real_centroid)
    has_gaia_source = "Gaia DR3 Source" in available
    has_gaia_astroparams = "Gaia DR3 Astrophysical Parameters" in available
    has_centroid = "MAST TESS FITS (light curve + centroid)" in available
    has_extended = any(c in available for c in
                        ("2MASS Photometry", "Pan-STARRS Photometry", "Spectroscopy (APOGEE/GALAH/LAMOST)"))

    if has_real_light_curve and has_centroid and has_extended and has_gaia_source and has_gaia_astroparams:
        tier, name = 3, "Full 4-branch net (light curve + centroid + extended catalogs)"
    elif has_real_light_curve and has_gaia_source and has_gaia_astroparams:
        tier, name = 2, "Global+Local CNN (real light curve)"
    elif has_gaia_source and has_gaia_astroparams:
        tier, name = 1, "RF tabular model (NASA/TOI + Gaia)"
    else:
        tier, name = 0, "Rule engine only"

    return TierResult(
        tier=tier,
        tier_name=name,
        catalogs_available=available,
        catalogs_missing=[c for c in CATALOG_NAMES if c not in available],
        catalogs_total=len(CATALOG_NAMES),
        coverage_fraction=round(len(available) / len(CATALOG_NAMES), 3),
    )
