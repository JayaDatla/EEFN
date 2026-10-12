"""Missing catalog values must not carry label information.

In the Kepler training set, missing stellar radius/Teff occurred ONLY for the
"Not Transit-Like" class (7/39 stars; 0/100 planets, 0/66 eclipsing binaries), so a naive
model learns "no stellar radius -> Not Transit-Like". In production ~20% of hosts have no
radius, and a known planet (TOI-104.01, SNR 127, clean odd/even, no secondary) was scored
90% Not Transit-Like purely because its host radius was missing.

The contract: removing stellar catalog inputs from an otherwise identical, clearly
planet-like light curve must not move the verdict away from planet.
"""
import os
import sys

import numpy as np
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml import lightcurve_features as LF
from app.ml.lightcurve_vetter import lightcurve_vetter

pytestmark = pytest.mark.skipif(not lightcurve_vetter.available, reason="vetter artifact not present")

PERIOD, DUR_H, T0 = 4.0873, 5.59, 2.0


def _clean_planet_lc(seed=0):
    rng = np.random.RandomState(seed)
    t = np.arange(0, 400.0, LF.KEPLER_LONG_CADENCE_DAYS)
    f = 1.0 + rng.normal(0, 3e-4, t.size)
    phase = ((t - T0 + PERIOD / 2) % PERIOD) - PERIOD / 2
    f[np.abs(phase) < DUR_H / 24 / 2] -= 0.0036
    return t, f


FULL = {"teff": 6100.0, "rstar": 1.3, "depth_ppm": 3600.0, "j_mag": 9.4, "k_mag": 9.1, "g_mag": 10.3, "r_mag": 10.0}
NO_STELLAR = {"depth_ppm": 3600.0}                       # host has no Teff/radius/photometry in the DB
NO_RADIUS_ONLY = {k: v for k, v in FULL.items() if k not in ("rstar", "teff")}


@pytest.mark.parametrize("stellar", [NO_STELLAR, NO_RADIUS_ONLY])
def test_missing_stellar_params_do_not_flip_a_clean_planet_to_not_transit_like(stellar):
    t, f = _clean_planet_lc()
    full = lightcurve_vetter.vet(t, f, PERIOD, T0, DUR_H, FULL)["classification"]
    missing = lightcurve_vetter.vet(t, f, PERIOD, T0, DUR_H, stellar)["classification"]
    # Missing inputs may add uncertainty, but must not systematically push toward "Not Transit-Like".
    assert missing["Not Transit-Like"] - full["Not Transit-Like"] < 0.15, (full, missing)
    assert full["Planet Transit"] - missing["Planet Transit"] < 0.20, (full, missing)
