"""Informational checks must never leak into the pre-registered flags (frozen prospective snapshot)."""
from types import SimpleNamespace

from app.science.flags import (
    CORE_FLAGS, INFORMATIONAL_FLAGS, THRESHOLDS, any_core_flag, compute_flags, compute_informational_flags,
)


def _host(**kw):
    base = dict(ruwe=None, rad=None, mass=None, teff=None, toi_teff=None, toi_rad=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _cand(**kw):
    base = dict(trandep=1000.0, orbper=4.0, trandurh=3.0)
    base.update(kw)
    return SimpleNamespace(**base)


def test_giant_planet_ambiguity_fires_above_the_reference_radius():
    # sqrt(0.01) * 1.0 Rsun * ~109 = ~10.9 R_Earth, above 8
    assert compute_informational_flags(_cand(trandep=10000.0), _host(rad=1.0))["giant_planet_ambiguity"] is True


def test_giant_planet_ambiguity_is_false_for_small_planets():
    # sqrt(0.001) * 1.0 * ~109 = ~3.4 R_Earth
    assert compute_informational_flags(_cand(trandep=1000.0), _host(rad=1.0))["giant_planet_ambiguity"] is False


def test_giant_planet_ambiguity_is_unknown_without_a_radius():
    assert compute_informational_flags(_cand(), _host())["giant_planet_ambiguity"] is None


def test_giant_planet_ambiguity_has_no_upper_bound():
    # Young brown dwarfs can be large, so the ambiguity flag stays on above the 22 R_Earth unphysical cut.
    big = compute_informational_flags(_cand(trandep=250000.0), _host(rad=5.0))
    assert big["giant_planet_ambiguity"] is True
    assert compute_flags(_cand(trandep=250000.0), _host(rad=5.0))["unphysical_radius"] is True


def test_informational_flags_do_not_change_the_pre_registered_flag_set():
    assert CORE_FLAGS == ["ruwe_likely_binary", "unphysical_radius", "density_inconsistent", "teff_outlier",
                          "radius_outlier"]
    assert "giant_planet_ambiguity" not in compute_flags(_cand(trandep=10000.0), _host(rad=1.0))
    assert not any(k.startswith("giant_planet") for k in THRESHOLDS)
    assert INFORMATIONAL_FLAGS == ["giant_planet_ambiguity"]


def test_a_giant_planet_alone_is_not_a_core_flag():
    flags = compute_flags(_cand(trandep=10000.0), _host(rad=1.0, ruwe=1.0, teff=5000.0, toi_teff=5050.0, toi_rad=1.0))
    assert compute_informational_flags(_cand(trandep=10000.0), _host(rad=1.0))["giant_planet_ambiguity"] is True
    assert any_core_flag(flags) is False
