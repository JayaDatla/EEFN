"""
Physics-motivated light-curve features for transit vetting.

Why this exists (see LIMITATIONS.md #7 and app/ml/dl_architecture_study.json): with ~150
labelled real stars a 3.9M-parameter CNN scored 57% in star-grouped cross-validation,
while gradient boosting on the handful of numbers an astronomer actually checks when
vetting a transit (is the dip the same depth on odd and even transits? is there a
secondary eclipse? is the bottom flat or V-shaped? is the implied planet radius
plausible?) scored 85%. This module is the single implementation of those features --
the training script and the serving path both call `build_feature_vector`, so they
cannot drift apart.

Inputs are expected in the lightkurve convention (BTJD for TESS, BKJD for Kepler); the
epoch `t0` must be in the same system as `time`.

Domain-transfer notes (the model is trained on Kepler, served on TESS):
* Everything is binned to the Kepler long cadence (~29.4 min) first, so per-point noise
  and the detrending window mean the same thing on both missions.
* Kepler-only inputs (Kepler magnitude) and baseline-length-dependent counts (number of
  transits, absolute out-of-transit scatter) are deliberately NOT features; dropping
  them cost 0.1 points of cross-validated accuracy, so there was no reason to keep a
  shortcut that wouldn't transfer.
* SNR-type features still scale with how many transits were observed (a 27-day TESS
  sector sees far fewer than 4 years of Kepler). Low-SNR tests are less able to flag an
  odd/even or secondary signal; that is physically correct but means the model's score
  on TESS is not calibrated the way it was on Kepler. See LIMITATIONS.md #7.
"""
import math
from typing import Dict, Optional, Tuple

import numpy as np

KEPLER_LONG_CADENCE_DAYS = 29.4 / 1440.0

FEATURE_NAMES = [
    "depth", "snr", "odd_even_sigma", "secondary_depth", "secondary_sigma",
    "secondary_ratio", "flatness", "log_period", "duration_h", "dur_over_period",
    "teff", "rstar", "catalog_depth_ppm", "implied_rp_earth", "dur_ratio",
    "j_k", "g_r", "g_k",
]

CLASS_NAMES = ["Planet Transit", "Eclipsing Binary", "Not Transit-Like"]


def rebin(time: np.ndarray, flux: np.ndarray, cadence_days: float = KEPLER_LONG_CADENCE_DAYS) -> Tuple[np.ndarray, np.ndarray]:
    """Average onto a uniform cadence; a no-op for data already at or coarser than it."""
    time, flux = np.asarray(time, float), np.asarray(flux, float)
    ok = np.isfinite(time) & np.isfinite(flux)
    time, flux = time[ok], flux[ok]
    if len(time) < 3 or np.median(np.diff(time)) >= 0.9 * cadence_days:
        return time, flux
    idx = np.floor((time - time[0]) / cadence_days).astype(np.int64)
    uniq, inv, counts = np.unique(idx, return_inverse=True, return_counts=True)
    t = np.bincount(inv, weights=time) / counts
    f = np.bincount(inv, weights=flux) / counts
    keep = counts >= max(1, int(0.5 * cadence_days / np.median(np.diff(time))))
    return t[keep], f[keep]


def detrend(time: np.ndarray, flux: np.ndarray, period: float, t0: float, dur_days: float) -> np.ndarray:
    """Median-filter detrending with the transits masked so the filter can't eat the dip.
    Window = max(3 transit durations, 0.75 d): wide enough to keep the transit shape."""
    from scipy.ndimage import median_filter
    phase = ((time - t0 + period / 2.0) % period) - period / 2.0
    in_tr = np.abs(phase) < 1.2 * dur_days
    flux = flux / np.nanmedian(flux)
    base = flux.copy()
    base[in_tr] = np.nan
    good = np.isfinite(base)
    if good.sum() < 50:
        return flux
    base = np.interp(time, time[good], base[good])
    cad = np.median(np.diff(time))
    win = int(max(3 * dur_days, 0.75) / cad) | 1
    out = flux / median_filter(base, size=win, mode="nearest")
    # Clip single-cadence upward outliers (cosmic rays / flares); never the dip itself.
    mad = 1.4826 * np.nanmedian(np.abs(out - np.nanmedian(out)))
    out[out > 1.0 + 6 * mad] = np.nan
    return out


def transit_stats(time: np.ndarray, flux: np.ndarray, period: float, t0: float, dur_days: float) -> Dict[str, float]:
    phase = ((time - t0 + period / 2.0) % period) - period / 2.0
    epoch = np.round((time - t0) / period).astype(int)
    ok = np.isfinite(flux)
    core = (np.abs(phase) < 0.25 * dur_days) & ok
    inn = (np.abs(phase) < 0.5 * dur_days) & ok
    oot = (np.abs(phase) > 1.5 * dur_days) & ok
    sec = (np.abs(np.abs(phase) - period / 2.0) < 0.5 * dur_days) & ok
    noise = np.nanstd(flux[oot]) if oot.sum() > 20 else np.nan
    nan = float("nan")

    def depth(mask):
        if mask.sum() < 3 or not np.isfinite(noise):
            return nan, nan
        return 1.0 - float(np.nanmedian(flux[mask])), noise / math.sqrt(mask.sum())

    d_core, e_core = depth(core)
    d_in, _ = depth(inn)
    do, eo = depth(core & (epoch % 2 == 1))
    de, ee = depth(core & (epoch % 2 == 0))
    ds, es = depth(sec)
    return {
        "depth": d_core,
        "snr": d_core / e_core if np.isfinite(e_core) and e_core > 0 else nan,
        "odd_even_sigma": abs(do - de) / math.hypot(eo, ee) if np.isfinite(do) and np.isfinite(de) else nan,
        "secondary_depth": ds,
        "secondary_sigma": ds / es if np.isfinite(ds) and es > 0 else nan,
        "secondary_ratio": ds / d_core if np.isfinite(ds) and np.isfinite(d_core) and d_core > 0 else nan,
        "flatness": d_core / d_in if np.isfinite(d_core) and np.isfinite(d_in) and d_in > 0 else nan,
    }


def stellar_features(period: float, duration_h: float, stellar: Dict[str, Optional[float]]) -> Dict[str, float]:
    nan = float("nan")

    def g(k):
        v = stellar.get(k)
        return float(v) if v is not None and np.isfinite(v) else nan

    rs, depth_ppm = g("rstar"), g("depth_ppm")
    exp_dur = 13.0 * (period / 365.25) ** (1 / 3) * rs ** (1 / 3) if np.isfinite(rs) and rs > 0 else nan
    return {
        "log_period": math.log10(period),
        "duration_h": duration_h,
        "dur_over_period": duration_h / 24.0 / period,
        "teff": g("teff"),
        "rstar": rs,
        "catalog_depth_ppm": depth_ppm,
        # Implied planet radius from the catalog depth; > ~22 R_Earth is not a planet.
        "implied_rp_earth": math.sqrt(max(depth_ppm, 0.0) * 1e-6) * rs * 109.2 if np.isfinite(depth_ppm) and np.isfinite(rs) else nan,
        "dur_ratio": duration_h / exp_dur if np.isfinite(exp_dur) and exp_dur > 0 else nan,
        "j_k": g("j_mag") - g("k_mag"),
        "g_r": g("g_mag") - g("r_mag"),
        "g_k": g("g_mag") - g("k_mag"),
    }


def build_feature_vector(
    time: np.ndarray, flux: np.ndarray, period: float, t0: float, duration_h: float,
    stellar: Optional[Dict[str, Optional[float]]] = None,
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Raw light curve -> (feature_vector, global_view, local_view), or None if the series
    is unusable. NaN marks a feature that could not be measured (LightGBM handles it
    natively; nothing is imputed with a plausible-looking default)."""
    from app.ml.deep_learning_pipeline import dl_vetting_engine

    stellar = stellar or {}
    dur_days = duration_h / 24.0
    if period <= 0 or dur_days <= 0 or period < 2.5 * dur_days or period < 0.3:
        return None
    t, f = rebin(time, flux)
    if len(t) < 100:
        return None
    flat = detrend(t, f, period, t0, dur_days)
    feats = {**transit_stats(t, flat, period, t0, dur_days), **stellar_features(period, duration_h, stellar)}
    ok = np.isfinite(flat)
    g, l = dl_vetting_engine.preprocess_lightcurve(t[ok], flat[ok], period, duration_h, t0)
    vec = np.array([feats[n] for n in FEATURE_NAMES], dtype=np.float64)
    return vec, (g - 1.0).astype(np.float32), (l - 1.0).astype(np.float32)
