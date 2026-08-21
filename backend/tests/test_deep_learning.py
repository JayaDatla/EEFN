import pytest
import numpy as np
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.deep_learning_pipeline import (
    dl_vetting_engine,
    DeepExoFusionNet,
    DeepLearningVettingEngine,
    DL_ARCHITECTURE_VERSION,
)
import torch

def test_deep_exofusion_net_forward():
    """
    Test the raw PyTorch neural network forward pass with dummy tensor inputs.
    """
    model = DeepExoFusionNet()
    
    # Dummy tensors
    batch_size = 4
    global_lc = torch.randn(batch_size, 1, 2001)
    local_lc = torch.randn(batch_size, 1, 201)
    centroid_drift = torch.randn(batch_size, 3, 201)
    metadata = torch.randn(batch_size, 28)

    logits = model(global_lc, local_lc, centroid_drift, metadata)
    assert logits.shape == (batch_size, 3)

def test_preprocess_lightcurve():
    """
    Test phase-folding and resampler grid shapes (2001 global bins, 201 local bins).
    """
    time = np.linspace(0.0, 10.0, 1000)
    # Simulate a simple flat light curve
    flux = np.ones_like(time)
    
    global_view, local_view = dl_vetting_engine.preprocess_lightcurve(
        time=time,
        flux=flux,
        period=3.0,
        duration_hours=2.0,
        t0=1.25
    )
    
    assert global_view.shape == (2001,)
    assert local_view.shape == (201,)
    # Output values should be close to 1.0
    assert np.allclose(global_view, 1.0)
    assert np.allclose(local_view, 1.0)

def test_vet_candidate():
    """
    Test the full vetting engine pipeline (preprocessing + model forward pass).
    """
    time = np.linspace(0.0, 20.0, 2000)
    # Simulate flat curve with small gaussian noise
    flux = 1.0 + np.random.normal(0.0, 0.001, len(time))
    
    stellar_params = {
        'st_teff': 5800.0,
        'st_rad': 1.0,
        'st_mass': 1.0,
        'st_logg': 4.4,
        'RUWE': 1.0,
        'parallax': 10.0,
        'derived_rp_diff': 0.05,
        'blending': 0.1
    }
    
    result = dl_vetting_engine.vet_candidate(
        time=time,
        detrended_flux=flux,
        period=4.5,
        duration_hours=3.0,
        stellar_params=stellar_params
    )
    
    # Assert keys exist
    assert "global_view" in result
    assert "local_view" in result
    assert "classification" in result
    assert "best_class" in result
    assert "confidence" in result
    
    # Assert dimensions
    assert len(result["global_view"]) == 2001
    assert len(result["local_view"]) == 201
    
    # Assert probability properties
    probs = result["classification"]
    assert len(probs) == 3
    for k, v in probs.items():
        assert 0.0 <= v <= 1.0
        
    total_prob = sum(probs.values())
    assert pytest.approx(total_prob) == 1.0

    # centroid_dx/centroid_dy were never supplied in stellar_params -- must be honestly
    # reported as unavailable rather than treated as a measured flat centroid (A.6).
    assert result["centroid_available"] is False


def test_engine_refuses_silent_fallback_on_legacy_checkpoint(tmp_path):
    """A checkpoint with no architecture_version tag (e.g. the old 3-branch/8-feature
    weights) must be rejected loudly, not partially loaded with strict=False -- fixes
    A.2's silent random-weight fallback."""
    legacy_checkpoint_path = tmp_path / "legacy_weights.pth"
    torch.save(DeepExoFusionNet().state_dict(), legacy_checkpoint_path)  # raw state_dict, no version tag

    engine = DeepLearningVettingEngine(model_weights_path=str(legacy_checkpoint_path))

    assert engine.degraded is True
    assert engine.model_status == "untrained_fallback"
    assert engine.load_error is not None


def test_engine_loads_version_matched_checkpoint(tmp_path):
    checkpoint_path = tmp_path / "versioned_weights.pth"
    model = DeepExoFusionNet()
    torch.save({
        "state_dict": model.state_dict(),
        "architecture_version": DL_ARCHITECTURE_VERSION,
        "trained_at": "test",
    }, checkpoint_path)

    engine = DeepLearningVettingEngine(model_weights_path=str(checkpoint_path))

    assert engine.degraded is False
    assert engine.model_status == "trained"
    assert engine.load_error is None


def test_vet_candidate_reports_centroid_available_when_supplied():
    time = np.linspace(0.0, 20.0, 2000)
    flux = 1.0 + np.random.normal(0.0, 0.001, len(time))

    result = dl_vetting_engine.vet_candidate(
        time=time, detrended_flux=flux, period=4.5, duration_hours=3.0,
        stellar_params={
            'st_teff': 5800.0, 'st_rad': 1.0, 'ruwe': 1.0,
            'centroid_dx': np.zeros(201).tolist(),
            'centroid_dy': np.zeros(201).tolist(),
        },
    )
    assert result["centroid_available"] is True


def test_metadata_vector_distinguishes_unmeasured_ruwe_from_measured_ruwe_of_one():
    """UPGRADE_PLAN.md A.6's second named example: missing RUWE defaulting to 1.0 reads
    as 'definitively a single star' to the network. The raw RUWE value is still defaulted
    to 1.0 for numerical stability, but the ruwe_present bit must differ between the
    two cases so they are not fed to the network as identical evidence."""
    vector_missing = dl_vetting_engine.build_metadata_vector({'st_teff': 5700.0, 'ruwe': None})
    vector_measured = dl_vetting_engine.build_metadata_vector({'st_teff': 5700.0, 'ruwe': 1.0})

    assert len(vector_missing) == len(vector_measured) == 28
    assert vector_missing[6] == vector_measured[6] == 1.0  # same raw RUWE value fed in
    ruwe_present_idx = 18
    assert vector_missing[ruwe_present_idx] == 0.0   # ruwe_present = False
    assert vector_measured[ruwe_present_idx] == 1.0  # ruwe_present = True


def test_metadata_vector_presence_bits_cover_every_optional_field():
    """UPGRADE_PLAN.md F.2: st_teff/st_rad/st_dist/j_mag/k_mag/h_mag/fe_h/g_mag/r_mag
    must each carry their own presence bit, not just RUWE (A.6's original named
    example) -- and F.5's new h_mag/g_mag/r_mag fields must be wired in too."""
    all_present = dl_vetting_engine.build_metadata_vector({
        'st_teff': 5700.0, 'st_rad': 1.0, 'st_dist': 100.0, 'ruwe': 1.0,
        'j_mag': 10.0, 'k_mag': 9.5, 'h_mag': 9.7, 'fe_h': 0.1,
        'g_mag': 12.0, 'r_mag': 11.5,
    })
    none_present = dl_vetting_engine.build_metadata_vector({})

    assert len(all_present) == len(none_present) == 28
    presence_indices = range(18, 28)  # ruwe_present through r_mag_present
    assert all(all_present[i] == 1.0 for i in presence_indices)
    assert all(none_present[i] == 0.0 for i in presence_indices)
    # Values still fall back to their physically-plausible defaults when unmeasured --
    # the presence bit is the honesty signal, not a change to the raw value slots.
    assert none_present[9] == pytest.approx(9.7 / 15.0)  # h_mag default
    assert none_present[10] == pytest.approx(12.0 / 20.0)  # g_mag default
