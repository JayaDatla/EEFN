import os
import sys
from types import SimpleNamespace

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pytest

from app.science.crossmatch import (RESIDUAL_THRESHOLD_MAG, TG_ROBUST_SIGMA_MAG, crossmatch_quality,
                                    expected_t_minus_g, tmag_gmag_residual)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV = os.path.join(REPO, "validation", "data", "validation_dataset.csv")


def _host(**kw):
    return SimpleNamespace(**{**dict(toi_tmag=None, gaia_g_mag=None, gaia_bp_rp=None, gaia_match_sep_arcsec=None), **kw})


@pytest.mark.skipif(not os.path.exists(CSV), reason="dataset missing")
def test_the_colour_relation_really_is_tight_on_the_project_data():
    """The whole test rests on T-G being a tight function of BP-RP; re-verify the claimed scatter."""
    d = pd.read_csv(CSV)[["st_tmag", "Gmag", "BPmag", "RPmag"]].dropna()
    resid = (d.st_tmag - d.Gmag) - d.apply(lambda r: expected_t_minus_g(r.BPmag - r.RPmag), axis=1)
    robust_sigma = 1.4826 * (resid - resid.median()).abs().median()
    assert robust_sigma < 0.03
    assert (resid.abs() > RESIDUAL_THRESHOLD_MAG).mean() < 0.05      # only a few percent flagged


def test_a_consistent_match_has_a_tiny_residual_and_a_mismatch_a_huge_one():
    bp_rp = 0.9
    g = 12.0
    t = g + expected_t_minus_g(bp_rp)
    assert abs(tmag_gmag_residual(t, g, bp_rp)) < 1e-9
    wrong_star = tmag_gmag_residual(t, g + 1.5, bp_rp)                # neighbour 1.5 mag fainter
    assert abs(wrong_star) > 100 * TG_ROBUST_SIGMA_MAG
    assert crossmatch_quality(_host(toi_tmag=t, gaia_g_mag=g + 1.5, gaia_bp_rp=bp_rp))["suspect"] is True
    assert crossmatch_quality(_host(toi_tmag=t, gaia_g_mag=g, gaia_bp_rp=bp_rp))["suspect"] is False


def test_missing_inputs_are_unknown_not_clean():
    assert crossmatch_quality(_host())["suspect"] is None
    assert tmag_gmag_residual(10.0, 10.5, None) is None
    assert tmag_gmag_residual(10.0, 10.5, 9.0) is None                  # colour outside the fitted range


def test_separation_is_used_only_when_the_photometric_test_cannot_run():
    assert crossmatch_quality(_host(gaia_match_sep_arcsec=4.2))["suspect"] is True       # no photometry: separation decides
    assert crossmatch_quality(_host(gaia_match_sep_arcsec=0.3))["suspect"] is False
    bp_rp, g = 0.9, 12.0
    t = g + expected_t_minus_g(bp_rp)
    consistent = crossmatch_quality(_host(toi_tmag=t, gaia_g_mag=g, gaia_bp_rp=bp_rp, gaia_match_sep_arcsec=3.5))
    assert consistent["suspect"] is False          # consistent photometry outweighs a 3.5 arcsec separation
