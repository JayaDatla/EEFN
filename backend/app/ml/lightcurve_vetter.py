"""
Serving side of the light-curve vetter (trained by validation/scripts/train_lightcurve_vetter.py).

Classifies a REAL light curve -- there is deliberately no code path here that accepts the
simulated light curves /transit_pipeline generates for its what-if playground: running a
vetting model on a curve synthesised from the candidate's own catalog period/depth just
reflects those numbers back and calls it evidence.

`status` is part of every result so a missing model is reported, never papered over.
"""
import logging
import os
import pickle
from typing import Any, Dict, Optional

import numpy as np

from app.ml import lightcurve_features as LF
from app.pipeline.errors import TransientCatalogError

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lightcurve_vetter.pkl")


class LightCurveVetter:
    def __init__(self, model_path: str = MODEL_PATH):
        self.model = None
        self.version: Optional[str] = None
        self.load_error: Optional[str] = None
        try:
            with open(model_path, "rb") as f:
                art = pickle.load(f)
            if art["feature_names"] != LF.FEATURE_NAMES:
                raise RuntimeError("model was trained on a different feature set than lightcurve_features.FEATURE_NAMES")
            self.model = art["model"]
            self.version = art["model_version"]
            self.meta = {k: art.get(k) for k in ("trained_at", "n_kois", "n_stars")}
        except Exception as e:  # missing file, version skew, corrupt pickle
            self.load_error = str(e)
            logger.error("LightCurveVetter unavailable (%s). Results will report model_status=unavailable.", e)

    @property
    def available(self) -> bool:
        return self.model is not None

    def vet(self, time: np.ndarray, flux: np.ndarray, period: float, t0: float, duration_h: float,
            stellar: Optional[Dict[str, Optional[float]]] = None) -> Dict[str, Any]:
        if not self.available:
            return {"model_status": "unavailable", "load_error": self.load_error}
        built = LF.build_feature_vector(time, flux, period, t0, duration_h, stellar)
        if built is None:
            return {"model_status": "unusable_lightcurve"}
        vec, g_view, l_view = built
        probs = self.model.predict_proba(vec.reshape(1, -1))[0]
        classification = {name: float(p) for name, p in zip(LF.CLASS_NAMES, probs)}
        best = max(classification, key=classification.get)
        return {
            "model_status": "trained",
            "model_version": self.version,
            "classification": classification,
            "best_class": best,
            "confidence": float(classification[best]),
            "features": {n: (None if not np.isfinite(v) else float(v)) for n, v in zip(LF.FEATURE_NAMES, vec)},
            "global_view": g_view.tolist(),
            "local_view": l_view.tolist(),
        }


def fetch_tess_lightcurve(tic_id: int, max_sectors: int = 3):
    """Real SPOC 2-minute PDCSAP light curve for a TIC, stitched over up to `max_sectors`
    sectors (spread across the baseline). Returns (time_btjd, flux, sectors) or None."""
    import lightkurve as lk
    import shutil
    import tempfile

    try:
        search = lk.search_lightcurve(f"TIC {int(tic_id)}", mission="TESS", author="SPOC", exptime=120)
    except Exception as e:
        logger.exception("MAST light-curve search failed for TIC %s", tic_id)
        raise TransientCatalogError(f"MAST light-curve search failed: {e}") from e
    if len(search) == 0:
        return None
    step = max(1, len(search) // max(1, max_sectors))
    picks = list(range(len(search)))[::step][:max_sectors]
    tmp = tempfile.mkdtemp(prefix=f"eefn_lc_{int(tic_id)}_")
    try:
        lcs, sectors, download_errors = [], [], 0
        for i in picks:
            try:
                lc = search[i].download(download_dir=tmp, quality_bitmask="default")
            except Exception:
                logger.exception("Light-curve download failed for TIC %s (item %s)", tic_id, i)
                download_errors += 1
                continue
            if lc is not None:
                lcs.append(lc.remove_nans().normalize())
                sectors.append(int(getattr(lc, "sector", 0) or 0))
        if not lcs:
            if download_errors == len(picks):
                raise TransientCatalogError(f"every light-curve download failed for TIC {tic_id}")
            return None
        try:
            stitched = lk.LightCurveCollection(lcs).stitch()
        except Exception as e:
            raise TransientCatalogError(f"light-curve stitching failed for TIC {tic_id}: {e}") from e
        return np.asarray(stitched.time.value, float), np.asarray(stitched.flux.value, float), sectors
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


lightcurve_vetter = LightCurveVetter()
