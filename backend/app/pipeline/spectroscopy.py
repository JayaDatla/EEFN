"""
UPGRADE_PLAN.md F.7: real spectroscopy cross-matching against APOGEE-2 DR17
(VizieR III/286, Abdurro'uf et al. 2022) -- the catalog previously listed as "never
actually built" in A.13 (a hardcoded Python dict in scratch/download_real_sample_data.py,
not a real API call).

APOGEE has limited sky coverage (it is a targeted spectroscopic survey, not an
all-sky one) -- most host stars will not have a match, and that is the correct,
honest outcome, not a bug. Every value this module returns came from a real VizieR
query; there is no synthetic fallback.
"""
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

APOGEE_DR17_CATALOG = "III/286"
MATCH_RADIUS_ARCSEC = 5.0


@dataclass
class SpectroscopyResult:
    teff_spec: Optional[float]
    fe_h: Optional[float]
    logg_spec: Optional[float]


def fetch_real_spectroscopy(ra_deg: float, dec_deg: float) -> Optional[SpectroscopyResult]:
    """
    Real VizieR cone-search cross-match against APOGEE-2 DR17 by coordinates. Returns
    None (never a fabricated/default value) if no match falls within the search radius,
    or if none of the returned rows carry a usable Teff/[Fe/H] value.
    """
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    try:
        vizier = Vizier(columns=["Teff", "e_Teff", "logg", "[Fe/H]", "e_[Fe/H]"])
        vizier.ROW_LIMIT = 1
        coord = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")
        result = vizier.query_region(coord, radius=MATCH_RADIUS_ARCSEC * u.arcsec, catalog=APOGEE_DR17_CATALOG)
    except Exception:
        logger.exception("APOGEE DR17 VizieR query failed for ra=%s dec=%s", ra_deg, dec_deg)
        return None

    if not result or len(result) == 0 or len(result[0]) == 0:
        return None

    row = result[0][0]
    teff = float(row["Teff"]) if "Teff" in row.colnames and row["Teff"] is not None and not _is_masked(row["Teff"]) else None
    logg = float(row["logg"]) if "logg" in row.colnames and row["logg"] is not None and not _is_masked(row["logg"]) else None
    fe_h_col = "[Fe/H]"
    fe_h = float(row[fe_h_col]) if fe_h_col in row.colnames and row[fe_h_col] is not None and not _is_masked(row[fe_h_col]) else None

    if teff is None and fe_h is None:
        return None

    return SpectroscopyResult(teff_spec=teff, fe_h=fe_h, logg_spec=logg)


def _is_masked(value) -> bool:
    try:
        return bool(getattr(value, "mask", False))
    except Exception:
        return False
