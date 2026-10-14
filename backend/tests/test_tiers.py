import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.models import ExoplanetCandidate, HostStar
from app.science.tiers import compute_model_tier, compute_catalog_availability, CATALOG_NAMES


def _candidate(centroid=None):
    return ExoplanetCandidate(pl_name="TOI-1.01", disposition="PC", centroid_shift_max=centroid)


def test_tier_0_when_no_host_star():
    """UPGRADE_PLAN.md F.1: a candidate with no cross-matched star at all must report
    Tier 0, not silently claim Tier 1 coverage it doesn't have."""
    result = compute_model_tier(_candidate(), host=None)
    assert result.tier == 0
    assert result.catalogs_available == ["NASA Exoplanet Archive/TOI"]
    assert len(result.catalogs_missing) == 6


def test_tier_1_when_gaia_source_and_astroparams_present():
    host = HostStar(hostname="TIC 1", ra=1.0, dec=1.0, parallax=10.0, ruwe=1.02, teff=5500.0, rad=1.0)
    result = compute_model_tier(_candidate(), host=host)
    assert result.tier == 1
    assert "Gaia DR3 Source" in result.catalogs_available
    assert "Gaia DR3 Astrophysical Parameters" in result.catalogs_available


def test_fabricated_seed_data_never_counts_as_real_catalog_coverage():
    """Regression test for a real bug found while building this: backend/seed_db.py
    fabricates centroid_shift_max and teff_spec/fe_h for demo candidates. Checking
    "is this field non-null" for availability would launder that fabrication into an
    availability claim -- exactly the dishonesty this feature exists to prevent.
    Setting the fields directly (as seed_db.py does) must NOT flip availability;
    only the explicit has_real_centroid/has_real_spectroscopy flags may."""
    host = HostStar(
        hostname="TIC 1", ra=1.0, dec=1.0, parallax=10.0, ruwe=1.02, teff=5500.0, rad=1.0,
        teff_spec=5510.0, fe_h=0.05,  # set exactly like seed_db.py's fabricated values
    )
    cand = _candidate(centroid=0.12)  # also set exactly like seed_db.py's fabricated values

    result = compute_model_tier(cand, host=host)  # no has_real_* flags passed -> all False
    assert "Spectroscopy (APOGEE/GALAH/LAMOST)" not in result.catalogs_available
    assert "MAST TESS FITS (light curve + centroid)" not in result.catalogs_available
    assert result.tier == 1


def test_tier_stays_1_without_a_real_light_curve_even_with_full_catalog_coverage():
    """No amount of catalog coverage bumps a candidate to Tier 2/3 without
    has_real_light_curve=True, because no real MAST light curve ingestion exists in
    this codebase yet (F.6 not built)."""
    host = HostStar(
        hostname="TIC 1", ra=1.0, dec=1.0, parallax=10.0, ruwe=1.02, teff=5500.0, rad=1.0,
        j_mag=10.0, g_mag=11.0,
    )
    result = compute_model_tier(_candidate(), host=host, has_real_light_curve=False)
    assert result.tier == 1
    assert result.tier_name == "Catalog model (NASA/TOI + Gaia)"


def test_tier_3_reachable_only_when_all_real_data_flags_and_coverage_are_true():
    host = HostStar(
        hostname="TIC 1", ra=1.0, dec=1.0, parallax=10.0, ruwe=1.02, teff=5500.0, rad=1.0,
        j_mag=10.0,
    )
    result = compute_model_tier(
        _candidate(), host=host,
        has_real_light_curve=True, has_real_centroid=True, has_real_spectroscopy=False,
    )
    assert result.tier == 3  # 2MASS alone satisfies the "extended catalogs" requirement


def test_tier_2_when_light_curve_real_but_no_centroid():
    host = HostStar(hostname="TIC 1", ra=1.0, dec=1.0, parallax=10.0, ruwe=1.02, teff=5500.0, rad=1.0)
    result = compute_model_tier(_candidate(), host=host, has_real_light_curve=True)
    assert result.tier == 2


def test_catalog_availability_never_exceeds_seven():
    host = HostStar(
        hostname="TIC 1", ra=1.0, dec=1.0, parallax=10.0, ruwe=1.02, teff=5500.0, rad=1.0,
        j_mag=10.0, g_mag=11.0,
    )
    available = compute_catalog_availability(
        _candidate(centroid=0.05), host, has_real_spectroscopy=True, has_real_centroid=True,
    )
    assert len(available) == len(CATALOG_NAMES) == 7
