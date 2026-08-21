import os
import sys

import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.train_deep_learning import _apply_metadata_dropout, METADATA_FIELD_DROPOUT_RATE, _OPTIONAL_METADATA_FIELDS
from app.ml.deep_learning_pipeline import dl_vetting_engine


FULL_TEMPLATE = {
    "st_teff": 5700.0, "st_rad": 1.1, "st_dist": 120.0, "ruwe": 1.05,
    "j_mag": 10.2, "k_mag": 9.5, "h_mag": 9.8, "g_mag": 12.1, "r_mag": 11.6,
    "fe_h": 0.1, "trandep": 1500.0,
}


def test_dropout_never_touches_required_fields():
    rng = np.random.RandomState(0)
    dropped = _apply_metadata_dropout(FULL_TEMPLATE, rng)
    assert dropped["trandep"] == 1500.0


def test_dropout_only_removes_present_optional_fields():
    rng = np.random.RandomState(1)
    template = {**FULL_TEMPLATE, "fe_h": None}
    dropped = _apply_metadata_dropout(template, rng)
    assert dropped["fe_h"] is None
    for field in _OPTIONAL_METADATA_FIELDS:
        assert dropped.get(field) is None or dropped.get(field) == FULL_TEMPLATE.get(field) or field == "fe_h"


def test_dropout_rate_is_approximately_correct_over_many_samples():
    rng = np.random.RandomState(42)
    drop_counts = 0
    trials = 2000
    for _ in range(trials):
        dropped = _apply_metadata_dropout(FULL_TEMPLATE, rng)
        if dropped["ruwe"] is None:
            drop_counts += 1
    observed_rate = drop_counts / trials
    assert abs(observed_rate - METADATA_FIELD_DROPOUT_RATE) < 0.05


def test_dropped_field_reflects_as_unmeasured_in_metadata_vector():
    rng = np.random.RandomState(7)
    # Force ruwe to drop by finding a seed where it does, deterministically.
    for seed in range(50):
        rng = np.random.RandomState(seed)
        dropped = _apply_metadata_dropout(FULL_TEMPLATE, rng)
        if dropped["ruwe"] is None:
            break
    assert dropped["ruwe"] is None
    vector_with_dropout = dl_vetting_engine.build_metadata_vector(dropped)
    vector_full = dl_vetting_engine.build_metadata_vector(FULL_TEMPLATE)
    # The two vectors must differ -- a dropped RUWE must not silently look identical
    # to a fully-measured one (this is the exact A.6 failure mode F.3 exists to avoid).
    assert vector_with_dropout != vector_full
