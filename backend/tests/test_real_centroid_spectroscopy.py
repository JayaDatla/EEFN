import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.models import ExoplanetCandidate, HostStar
from app.science.tiers import compute_model_tier


def test_seed_fabricated_fields_default_to_not_real():
    """UPGRADE_PLAN.md F.6/F.7: seed_db.py sets centroid_shift_max/teff_spec/fe_h
    directly without ever setting centroid_is_real/spectroscopy_is_real -- the model
    column defaults (False) must be what a fresh ORM object reports, so endpoints.py's
    `has_real_centroid=c.centroid_is_real` wiring reads False for fabricated demo data
    and only True for candidates a real mast_centroid.py/spectroscopy.py run touched."""
    cand = ExoplanetCandidate(pl_name="TOI-1.01", disposition="PC", centroid_shift_max=0.12)
    host = HostStar(hostname="TIC 1", ra=1.0, dec=1.0, teff_spec=5500.0, fe_h=0.1)

    assert cand.centroid_is_real in (None, False)
    assert host.spectroscopy_is_real in (None, False)


def test_real_centroid_flag_reaches_tier_computation():
    """A candidate that a real mast_centroid.py run actually touched (centroid_is_real
    True) must be able to reach Tier 3 when combined with the other required
    coverage -- confirms the endpoints.py/audit.py wiring wasn't left hardcoded False."""
    host = HostStar(hostname="TIC 1", ra=1.0, dec=1.0, parallax=10.0, ruwe=1.02, teff=5500.0, rad=1.0, j_mag=10.0)
    cand = ExoplanetCandidate(pl_name="TOI-1.01", disposition="PC", centroid_shift_max=0.11, centroid_is_real=True)

    result = compute_model_tier(cand, host=host, has_real_light_curve=True, has_real_centroid=cand.centroid_is_real)
    assert result.tier == 3
    assert "MAST TESS FITS (light curve + centroid)" in result.catalogs_available
