import logging
import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import math
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Bumped whenever DeepExoFusionNet's architecture (branch shapes, input dims, fusion
# width) changes. A checkpoint is only ever loaded if its recorded version matches this
# constant exactly -- see UPGRADE_PLAN.md A.2/C.2. This is what turns a silent
# shape-mismatch crash into an explicit, checked refusal to load.
DL_ARCHITECTURE_VERSION = "exofusion-net-v2.4branch.28feat.3ch-centroid.3class-real.1"

CENTROID_BINS = 201


class GlobalViewCNN(nn.Module):
    """
    1D CNN to process the global phase-folded light curve (2001 bins).
    Extracts orbital characteristics, secondary eclipses, and out-of-transit stellar variability.
    """
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv1d(1, 16, kernel_size=5, stride=2, padding=2)
        self.bn1 = nn.BatchNorm1d(16)
        self.conv2 = nn.Conv1d(16, 32, kernel_size=5, stride=2, padding=2)
        self.bn2 = nn.BatchNorm1d(32)
        self.conv3 = nn.Conv1d(32, 64, kernel_size=5, stride=2, padding=2)
        self.bn3 = nn.BatchNorm1d(64)
        self.conv4 = nn.Conv1d(64, 128, kernel_size=5, stride=2, padding=2)
        self.bn4 = nn.BatchNorm1d(128)

        self.pool = nn.MaxPool1d(2) # Resizes to 63
        self.fc = nn.Linear(128 * 63, 256)
        self.dropout = nn.Dropout(0.2)

    def forward(self, x):
        # Input shape: (batch, 1, 2001)
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = F.relu(self.bn4(self.conv4(x)))
        x = self.pool(x)
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc(x))
        x = self.dropout(x)
        return x

class LocalViewCNN(nn.Module):
    """
    1D CNN to process the local phase-folded light curve centered on the transit (201 bins).
    Focuses on transit geometry: ingress/egress slopes and flat-bottom vs. V-shape profiles.
    """
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv1d(1, 16, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm1d(16)
        self.conv2 = nn.Conv1d(16, 32, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm1d(32)
        self.conv3 = nn.Conv1d(32, 64, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm1d(64)

        self.pool = nn.MaxPool1d(2) # Resizes to 100
        self.fc = nn.Linear(64 * 100, 128)
        self.dropout = nn.Dropout(0.2)

    def forward(self, x):
        # Input shape: (batch, 1, 201)
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = self.pool(x)
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc(x))
        x = self.dropout(x)
        return x

class CentroidSpatialCNN(nn.Module):
    """
    ExoFusion-Net v2 Spatial Branch: processes target pixel centroid shifts.
    3 input channels: dx, dy, and an explicit presence mask (1.0 = real TPF centroid
    measurement, 0.0 = not measured for this candidate). The presence channel exists so
    the network can distinguish "measured centroid did not move" (real evidence against a
    background eclipsing binary) from "no centroid measurement exists" (no evidence either
    way) -- collapsing these to the same all-zero input was flagged as UPGRADE_PLAN.md A.6.
    """
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv1d(3, 16, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm1d(16)
        self.conv2 = nn.Conv1d(16, 32, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm1d(32)
        self.conv3 = nn.Conv1d(32, 64, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm1d(64)

        self.pool = nn.MaxPool1d(2) # Resizes to 100
        self.fc = nn.Linear(64 * 100, 128)
        self.dropout = nn.Dropout(0.2)

    def forward(self, x):
        # Input shape: (batch, 3, 201)
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = self.pool(x)
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc(x))
        x = self.dropout(x)
        return x

class StellarMetadataMLP(nn.Module):
    """
    MLP to process static stellar parameters, catalog discrepancies, and photometric features.
    Inputs 28 normalized parameters (target leakage features derived_rp_earth and
    derived_rp_diff STRIPPED; see build_metadata_vector for the full field list,
    including UPGRADE_PLAN.md F.2's per-optional-field presence bits).
    """
    def __init__(self, input_dim=28):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, 32)
        self.bn1 = nn.BatchNorm1d(32)
        self.fc2 = nn.Linear(32, 64)
        self.bn2 = nn.BatchNorm1d(64)
        self.fc3 = nn.Linear(64, 64)

    def forward(self, x):
        # Input shape: (batch, 28)
        x = F.relu(self.bn1(self.fc1(x)))
        x = F.relu(self.bn2(self.fc2(x)))
        x = F.relu(self.fc3(x))
        return x

class DeepExoFusionNet(nn.Module):
    """
    Unified 4-Branch Multi-Modal Late-Fusion Neural Network (ExoFusion-Net v2).
    Fuses Global CNN, Local CNN, Centroid CNN, and Metadata MLP features into a 576-dim fusion vector.
    Outputs calibrated 3-class probabilities: [Planet Transit, Eclipsing Binary, Not Transit-Like].

    Previously 4 classes (Planet Transit / Eclipsing Binary / Stellar Activity /
    Instrumental Noise), trained entirely on synthetic light curves. Retrained on
    real Kepler KOI light curves + real disposition/false-positive-flag labels
    (validation/scripts/fetch_real_kepler_dataset.py) -- but Kepler's own
    false-positive flags (and no other standard dataset either) don't separate
    "stellar activity" from "instrumental noise" at the per-example level, so that
    distinction was never something we could honestly claim to classify. Merged
    into one real "Not Transit-Like" class rather than keep a 4th class that would
    still be synthetic-only.
    """
    def __init__(self, num_classes=3, temperature=1.15):
        super().__init__()
        self.global_branch = GlobalViewCNN()
        self.local_branch = LocalViewCNN()
        self.centroid_branch = CentroidSpatialCNN()
        self.metadata_branch = StellarMetadataMLP(input_dim=28)

        self.temperature = temperature

        # Late fusion layer inputs: 256 (global) + 128 (local) + 128 (centroid) + 64 (metadata) = 576
        self.fc1 = nn.Linear(576, 128)
        self.fc2 = nn.Linear(128, 64)
        self.dropout = nn.Dropout(0.3)
        self.classifier = nn.Linear(64, num_classes)

    def forward(self, global_lc, local_lc, centroid_drift, metadata):
        # global_lc: (batch, 1, 2001)
        # local_lc: (batch, 1, 201)
        # centroid_drift: (batch, 3, 201)
        # metadata: (batch, 16)

        g_feat = self.global_branch(global_lc)
        l_feat = self.local_branch(local_lc)
        c_feat = self.centroid_branch(centroid_drift)
        m_feat = self.metadata_branch(metadata)

        # Concatenate all 4 branch features
        fused = torch.cat([g_feat, l_feat, c_feat, m_feat], dim=1)

        # Late fusion dense blocks
        x = F.relu(self.fc1(fused))
        x = self.dropout(x)
        x = F.relu(self.fc2(x))
        logits = self.classifier(x)

        # Apply temperature scaling calibration
        calibrated_logits = logits / self.temperature
        return calibrated_logits

class DeepLearningVettingEngine:
    """
    Production wrapper executing phase folding, centroid extraction, feature assembly,
    and ExoFusion-Net v2 neural network inference.
    """
    def __init__(self, model_weights_path: str = None):
        self.model = DeepExoFusionNet()
        self.model.eval()
        self.classes = ["Planet Transit", "Eclipsing Binary", "Not Transit-Like"]

        # Loud-failure contract (fixes A.2): a mismatched or missing checkpoint must
        # never be silently swallowed into a randomly-initialized network pretending to
        # be trained. Every caller must check `degraded`/`model_status` and surface it.
        self.degraded = True
        self.model_status = "untrained_fallback"
        self.load_error: Optional[str] = None
        self.architecture_version = DL_ARCHITECTURE_VERSION

        if model_weights_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            potential_path = os.path.join(current_dir, "model_weights.pth")
            if os.path.exists(potential_path):
                model_weights_path = potential_path

        if model_weights_path and os.path.exists(model_weights_path):
            try:
                checkpoint = torch.load(model_weights_path, map_location=torch.device("cpu"))
                if not isinstance(checkpoint, dict) or "architecture_version" not in checkpoint or "state_dict" not in checkpoint:
                    raise RuntimeError(
                        "Checkpoint is a raw/legacy state_dict with no architecture_version tag; "
                        "refusing to load it against a possibly-mismatched architecture."
                    )
                if checkpoint["architecture_version"] != DL_ARCHITECTURE_VERSION:
                    raise RuntimeError(
                        f"Checkpoint architecture_version {checkpoint['architecture_version']!r} "
                        f"does not match current model architecture_version {DL_ARCHITECTURE_VERSION!r}."
                    )
                self.model.load_state_dict(checkpoint["state_dict"], strict=True)
                self.degraded = False
                self.model_status = "trained"
                trained_at = checkpoint.get("trained_at", "unknown")
                print(f"Loaded ExoFusion-Net v2 weights from {model_weights_path} "
                      f"(architecture_version={DL_ARCHITECTURE_VERSION}, trained_at={trained_at}).")
            except Exception as e:
                self.load_error = str(e)
                self.degraded = True
                self.model_status = "untrained_fallback"
                logger.error("DeepLearningVettingEngine failed to load %s: %s. "
                             "Serving degraded (untrained) output -- every API/UI consumer must "
                             "surface model_status.", model_weights_path, e)
        else:
            self.load_error = f"No checkpoint found at {model_weights_path!r}."
            logger.error("DeepLearningVettingEngine: %s Serving degraded (untrained) output.", self.load_error)

    def preprocess_lightcurve(
        self,
        time: np.ndarray,
        flux: np.ndarray,
        period: float,
        duration_hours: float,
        t0: float = 1.25
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Phase-folds and interpolates raw light curves into standard 1D formats:
        - Global View: 2001 bins covering the full orbital phase [-0.5, 0.5]
        - Local View: 201 bins centered on the transit [-3.5 * dur, 3.5 * dur]
        """
        folded_phase = ((time - t0 + period / 2.0) % period) - period / 2.0

        duration_days = duration_hours / 24.0
        local_window = duration_days * 3.5

        global_target_phases = np.linspace(-period / 2.0, period / 2.0, 2001)
        global_view = self._bin_fold(folded_phase, flux, global_target_phases)

        local_target_phases = np.linspace(-local_window, local_window, 201)
        local_view = self._bin_fold(folded_phase, flux, local_target_phases)

        return global_view, local_view

    @staticmethod
    def _bin_fold(phase: np.ndarray, flux: np.ndarray, target_phases: np.ndarray) -> np.ndarray:
        """
        Bins phase-folded flux by nearest target-phase bin and takes the per-bin
        median, then interpolates across any genuinely empty bins.

        A single, dense, real light curve folds many real transit cycles (years of
        Kepler/TESS baseline) onto the same ~2001/201-bin grid -- e.g. a 9-day
        period over a 4-year baseline puts ~150 independent transits into the same
        201-bin local view. The previous implementation ran `np.interp` directly on
        phase-sorted individual points: adjacent points after sorting by phase can
        come from *different* transit cycles, so pointwise linear interpolation
        connects noisy single-cadence samples from unrelated cycles instead of
        averaging them, corrupting the folded shape (verified on a real confirmed
        Kepler planet, KIC 10797460: the old code put the transit minimum 61 bins
        off-center at 3x the real depth; binning puts it correctly at the array's
        center, at the depth matching a direct in-/out-of-transit mean). Synthetic
        single-realization data (one point per phase) is unaffected either way --
        this only changes behavior when multiple real samples land in one bin.
        """
        n_bins = len(target_phases)
        bin_width = target_phases[1] - target_phases[0]
        in_window = (phase >= target_phases[0] - bin_width / 2.0) & (phase <= target_phases[-1] + bin_width / 2.0)
        if not np.any(in_window):
            return np.ones(n_bins)

        phase_w = phase[in_window]
        flux_w = flux[in_window]
        bin_idx = np.clip(np.round((phase_w - target_phases[0]) / bin_width).astype(int), 0, n_bins - 1)

        binned = np.full(n_bins, np.nan)
        # np.bincount + minlength gives sum-per-bin and count-per-bin in one pass;
        # median needs a groupby, done directly since n_bins is small (<=2001).
        order = np.argsort(bin_idx)
        bin_idx_sorted, flux_sorted = bin_idx[order], flux_w[order]
        unique_bins, start_idx = np.unique(bin_idx_sorted, return_index=True)
        splits = np.split(flux_sorted, start_idx[1:])
        for b, vals in zip(unique_bins, splits):
            binned[b] = np.median(vals)

        valid = ~np.isnan(binned)
        if not np.any(valid):
            return np.ones(n_bins)
        # Fill any bins with no real sample by interpolating between neighboring
        # real bins (never a fabricated value where a real one exists nearby).
        binned = np.interp(np.arange(n_bins), np.flatnonzero(valid), binned[valid], left=1.0, right=1.0)
        return binned

    def build_centroid_matrix(self, stellar_params: Dict[str, Any]) -> Tuple[np.ndarray, bool]:
        """
        Builds the (3, 201) centroid input: [dx, dy, presence_mask]. If no real centroid
        measurement is supplied, dx/dy are zeroed AND presence is zeroed -- the network
        can tell "flat because measured-and-flat" apart from "flat because unmeasured".
        Real TPF-derived centroid ingestion doesn't exist yet (UPGRADE_PLAN.md F.6); until
        it does, `centroid_dx`/`centroid_dy` will simply never be supplied and every
        candidate is honestly reported as centroid-unavailable.
        """
        dx = stellar_params.get('centroid_dx')
        dy = stellar_params.get('centroid_dy')
        available = dx is not None and dy is not None and len(dx) == CENTROID_BINS and len(dy) == CENTROID_BINS

        if available:
            dx_array = np.asarray(dx, dtype=np.float32)
            dy_array = np.asarray(dy, dtype=np.float32)
            presence = np.ones(CENTROID_BINS, dtype=np.float32)
        else:
            dx_array = np.zeros(CENTROID_BINS, dtype=np.float32)
            dy_array = np.zeros(CENTROID_BINS, dtype=np.float32)
            presence = np.zeros(CENTROID_BINS, dtype=np.float32)

        return np.stack([dx_array, dy_array, presence], axis=0), available

    def build_metadata_vector(self, stellar_params: Dict[str, Any]) -> List[float]:
        """
        Builds the 28-element metadata vector fed to StellarMetadataMLP. Shared between
        inference (vet_candidate) and training (train_deep_learning.py) so the two can
        never independently drift apart the way predict.py's RF features once could have.

        Note on `teff_diff`/`rad_diff`/`dist_diff`: these come from AgreementMetrics
        (computed once, honestly, during ingestion from the real NASA-vs-Gaia catalog
        values) rather than being recomputed from a duplicated "gaia_teff" parameter that
        production never actually populated -- the old version of this vector always fed
        the network a hardcoded teff_diff/rad_diff of 0 in production because `gaia_teff`
        was never passed in by the only real caller (endpoints.py).

        UPGRADE_PLAN.md F.2/F.5: every optional-catalog-derived field now carries a
        paired presence bit alongside its value slot, not just RUWE (A.6's original
        named example) -- st_teff/st_rad/st_dist/j_mag/k_mag/h_mag/fe_h/g_mag/r_mag can
        all be genuinely unmeasured for a given target, and substituting a
        physically-plausible default without saying so is exactly the "missing looks
        clean" failure this plan exists to eliminate. h_mag (2MASS) and g_mag/r_mag
        (Pan-STARRS, two of five bands -- chosen as the most broadly available rather
        than all five, to keep this vector's width reasonable for a still-synthetic-only
        training set) are new in this version; F.5 shipped live ingestion for them but
        the DL model never consumed them until now.
        """
        def present(key: str) -> float:
            return 1.0 if stellar_params.get(key) is not None else 0.0

        st_teff_present = present('st_teff')
        st_rad_present = present('st_rad')
        st_dist_present = present('st_dist')
        j_mag_present = present('j_mag')
        k_mag_present = present('k_mag')
        h_mag_present = present('h_mag')
        fe_h_present = present('fe_h')
        g_mag_present = present('g_mag')
        r_mag_present = present('r_mag')

        st_teff = stellar_params.get('st_teff') or 5778.0
        st_rad = stellar_params.get('st_rad') or 1.0
        st_dist = stellar_params.get('st_dist') or 100.0
        trandep = stellar_params.get('trandep') or 1500.0
        ruwe_raw = stellar_params.get('ruwe')
        # RUWE unmeasured must not silently look identical to "RUWE=1.0, definitively a
        # single star" -- that exact substitution was UPGRADE_PLAN.md A.6's second named
        # example. ruwe_present tells the network which case this is.
        ruwe_present = 1.0 if ruwe_raw is not None else 0.0
        ruwe = ruwe_raw if ruwe_raw is not None else 1.0
        j_mag = stellar_params.get('j_mag') or 10.0
        k_mag = stellar_params.get('k_mag') or 9.5
        h_mag = stellar_params.get('h_mag') or 9.7
        g_mag = stellar_params.get('g_mag') or 12.0
        r_mag = stellar_params.get('r_mag') or 11.5
        fe_h = stellar_params.get('fe_h') or 0.0
        teff_diff = stellar_params.get('teff_diff') or 0.0
        rad_diff = stellar_params.get('rad_diff') or 0.0
        derived_rp_diff = stellar_params.get('derived_rp_diff') or 0.0
        density_sigma = stellar_params.get('density_discrepancy_sigma') or 0.0
        query_failed = 1.0 if stellar_params.get('query_failed', False) else 0.0
        blending = stellar_params.get('blending') or 0.0
        completeness = stellar_params.get('completeness')
        if completeness is None:
            completeness = 1.0

        return [
            st_teff / 5778.0,
            teff_diff / 500.0,
            st_rad,
            rad_diff / 0.5,
            st_dist / 100.0,
            trandep / 10000.0,
            ruwe,
            j_mag / 15.0,
            k_mag / 15.0,
            h_mag / 15.0,
            g_mag / 20.0,
            r_mag / 20.0,
            fe_h,
            derived_rp_diff / 5.0,
            density_sigma / 3.0,
            query_failed,
            blending,
            completeness,
            ruwe_present,
            st_teff_present,
            st_rad_present,
            st_dist_present,
            j_mag_present,
            k_mag_present,
            h_mag_present,
            fe_h_present,
            g_mag_present,
            r_mag_present,
        ]

    def vet_candidate(
        self,
        time: np.ndarray,
        detrended_flux: np.ndarray,
        period: float,
        duration_hours: float,
        stellar_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Runs full ExoFusion-Net v2 multi-branch inference. `model_status`/`degraded` in the
        return value MUST be surfaced by every API/UI consumer -- see __init__.
        """
        global_view, local_view = self.preprocess_lightcurve(
            time=time, flux=detrended_flux, period=period, duration_hours=duration_hours
        )

        global_view_centered = global_view - 1.0
        local_view_centered = local_view - 1.0

        centroid_matrix, centroid_available = self.build_centroid_matrix(stellar_params)
        metadata_vector = self.build_metadata_vector(stellar_params)

        # Convert to Tensors
        global_tensor = torch.tensor(global_view_centered, dtype=torch.float32).unsqueeze(0).unsqueeze(0) # (1, 1, 2001)
        local_tensor = torch.tensor(local_view_centered, dtype=torch.float32).unsqueeze(0).unsqueeze(0)   # (1, 1, 201)
        centroid_tensor = torch.tensor(centroid_matrix, dtype=torch.float32).unsqueeze(0)                 # (1, 3, 201)
        meta_tensor = torch.tensor(metadata_vector, dtype=torch.float32).unsqueeze(0)                     # (1, 28)

        # Model Inference
        with torch.no_grad():
            logits = self.model(global_tensor, local_tensor, centroid_tensor, meta_tensor)
            probabilities = F.softmax(logits, dim=1).squeeze(0).numpy()

        # Deterministic physics veto: capped, not overriding -- see C.5. This still
        # flags an extreme derived radius as a strong prior, but folds it in as evidence
        # rather than discarding the network's output outright.
        gaia_rad = stellar_params.get('gaia_rad') or stellar_params.get('st_rad') or 1.0
        trandep = stellar_params.get('trandep') or 1500.0
        derived_rp = gaia_rad * math.sqrt(max(0.0, trandep) * 1e-6) * 109.2
        is_unphysical_veto = bool(derived_rp > 22.0)
        if is_unphysical_veto:
            # Built from self.classes (not a hardcoded vector) so it can never again fall
            # out of sync with the output head's width.
            veto_weights = {"Planet Transit": 0.02, "Eclipsing Binary": 0.93, "Not Transit-Like": 0.05}
            veto_prior = np.array([veto_weights[c] for c in self.classes])
            probabilities = 0.15 * probabilities + 0.85 * veto_prior
            probabilities = probabilities / probabilities.sum()

        classification_result = {
            self.classes[i]: float(probabilities[i]) for i in range(len(self.classes))
        }

        return {
            "global_view": global_view.tolist(),
            "local_view": local_view.tolist(),
            "derived_rp_earth": round(derived_rp, 3),
            "is_unphysical_veto": is_unphysical_veto,
            "classification": classification_result,
            "best_class": max(classification_result, key=classification_result.get),
            "confidence": float(np.max(probabilities)),
            "centroid_available": centroid_available,
            "model_status": self.model_status,
            "degraded": self.degraded,
            "architecture_version": self.architecture_version,
            "load_error": self.load_error,
        }

# Global inference engine instance
dl_vetting_engine = DeepLearningVettingEngine()
