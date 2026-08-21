import os
import sys
import json
from collections import Counter
from datetime import datetime, timezone

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.ml.deep_learning_pipeline import dl_vetting_engine, DeepExoFusionNet, DL_ARCHITECTURE_VERSION

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REAL_DATASET_PATH = os.path.join(REPO_ROOT, "validation", "data", "real_kepler_training_set.npz")
REAL_METADATA_PATH = os.path.join(REPO_ROOT, "validation", "data", "real_kepler_training_set_metadata.json")

CLASS_NAMES = ["Planet Transit", "Eclipsing Binary", "Not Transit-Like"]

# UPGRADE_PLAN.md F.3: independently drop each optional-catalog metadata field with
# this probability per augmented sample, so the network sees more missingness-pattern
# variety than any one real star's fixed coverage pattern alone would offer.
METADATA_FIELD_DROPOUT_RATE = 0.25
_OPTIONAL_METADATA_FIELDS = (
    "st_teff", "st_rad", "st_dist", "ruwe", "j_mag", "k_mag", "h_mag", "g_mag", "r_mag", "fe_h",
)
AUGMENTATIONS_PER_STAR = 4


def _apply_metadata_dropout(metadata_template: dict, rng: np.random.RandomState) -> dict:
    dropped = dict(metadata_template)
    for field in _OPTIONAL_METADATA_FIELDS:
        if dropped.get(field) is not None and rng.uniform() < METADATA_FIELD_DROPOUT_RATE:
            dropped[field] = None
    return dropped


class ExoplanetDataset(Dataset):
    def __init__(self, data_list):
        self.data_list = data_list

    def __len__(self):
        return len(self.data_list)

    def __getitem__(self, idx):
        global_view, local_view, centroid_matrix, metadata, label = self.data_list[idx]
        return (
            torch.tensor(global_view, dtype=torch.float32).unsqueeze(0),   # (1, 2001)
            torch.tensor(local_view, dtype=torch.float32).unsqueeze(0),    # (1, 201)
            torch.tensor(centroid_matrix, dtype=torch.float32),            # (3, 201)
            torch.tensor(metadata, dtype=torch.float32),                   # (28)
            torch.tensor(label, dtype=torch.long),
        )


def load_real_dataset(rng: np.random.RandomState):
    """
    Loads the real Kepler light curves + real disposition/false-positive-flag
    labels built by validation/scripts/fetch_real_kepler_dataset.py. Refuses to
    run (rather than silently falling back to synthetic data) if that dataset
    hasn't been built yet -- see LIMITATIONS.md #7 for why "trained on synthetic
    light curves" was worth fixing rather than disclosing indefinitely.

    Real light curve arrays are fixed per real star (there is only one real
    measurement); AUGMENTATIONS_PER_STAR copies per star vary only the metadata
    presence pattern (dropout) and centroid presence, matching the synthetic
    path's original augmentation strategy for everything that isn't itself the
    measurement.
    """
    if not os.path.exists(REAL_DATASET_PATH):
        raise RuntimeError(
            f"No real training data at {REAL_DATASET_PATH}. Run "
            "`python validation/scripts/fetch_real_kepler_dataset.py --per-class N` first."
        )
    d = np.load(REAL_DATASET_PATH)
    with open(REAL_METADATA_PATH) as f:
        raw_metadata = json.load(f)

    global_views, local_views, centroids, star_labels = (
        d["global_views"], d["local_views"], d["centroids"], d["labels"]
    )
    n_stars = len(star_labels)

    data_list = []
    for i in range(n_stars):
        for _ in range(AUGMENTATIONS_PER_STAR):
            sample_meta = _apply_metadata_dropout(raw_metadata[i], rng)
            metadata_vector = dl_vetting_engine.build_metadata_vector(sample_meta)
            data_list.append((
                global_views[i], local_views[i], centroids[i].copy(),
                np.array(metadata_vector, dtype=np.float32), int(star_labels[i]),
            ))
    return data_list, n_stars, star_labels


def split_train_test(n_stars: int, star_labels: np.ndarray, rng: np.random.RandomState, test_frac: float = 0.2):
    """Stratified by class, at the *star* level (not per augmented sample) -- every
    augmented copy of a given real star stays on the same side of the split, or the
    held-out "test" set would just be memorized copies of training stars."""
    test_star_idx = set()
    for c in np.unique(star_labels):
        idxs = np.flatnonzero(star_labels == c)
        rng.shuffle(idxs)
        n_test = max(1, int(round(len(idxs) * test_frac)))
        test_star_idx.update(idxs[:n_test].tolist())
    return test_star_idx


def evaluate(model, dataloader) -> dict:
    model.eval()
    correct, total = 0, 0
    per_class_correct = Counter()
    per_class_total = Counter()
    with torch.no_grad():
        for global_lc, local_lc, centroid_drift, metadata, labels in dataloader:
            outputs = model(global_lc, local_lc, centroid_drift, metadata)
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            for lbl, pred in zip(labels.tolist(), predicted.tolist()):
                per_class_total[lbl] += 1
                if lbl == pred:
                    per_class_correct[lbl] += 1
    return {
        "accuracy": correct / total if total else 0.0,
        "n": total,
        "per_class_accuracy": {
            CLASS_NAMES[c]: (per_class_correct[c] / per_class_total[c] if per_class_total[c] else None)
            for c in range(len(CLASS_NAMES))
        },
        "per_class_n": {CLASS_NAMES[c]: per_class_total[c] for c in range(len(CLASS_NAMES))},
    }


def train_model():
    rng = np.random.RandomState(42)
    data_list, n_stars, star_labels = load_real_dataset(rng)
    print(f"Loaded {n_stars} real Kepler stars -> {len(data_list)} training samples "
          f"after {AUGMENTATIONS_PER_STAR}x metadata-dropout augmentation.")
    print("Real star class distribution:", Counter(star_labels.tolist()))

    split_rng = np.random.RandomState(7)
    test_star_idx = split_train_test(n_stars, star_labels, split_rng)

    train_data, test_data = [], []
    for i, sample in enumerate(data_list):
        star_i = i // AUGMENTATIONS_PER_STAR
        (test_data if star_i in test_star_idx else train_data).append(sample)

    print(f"Train samples: {len(train_data)} | Held-out test samples: {len(test_data)} "
          f"({len(test_star_idx)}/{n_stars} real stars held out, never trained on)")

    if len(train_data) == 0 or len(test_data) == 0:
        raise RuntimeError("Not enough real data for a train/test split -- fetch more stars first.")

    train_loader = DataLoader(ExoplanetDataset(train_data), batch_size=16, shuffle=True)
    test_loader = DataLoader(ExoplanetDataset(test_data), batch_size=16, shuffle=False)

    model = DeepExoFusionNet(num_classes=len(CLASS_NAMES))
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    print("Starting training loop...")
    num_epochs = 35
    final_train_accuracy = 0.0
    final_train_loss = 0.0
    for epoch in range(num_epochs):
        model.train()
        epoch_loss = 0.0
        correct = 0
        total = 0
        for global_lc, local_lc, centroid_drift, metadata, labels in train_loader:
            optimizer.zero_grad()
            outputs = model(global_lc, local_lc, centroid_drift, metadata)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item() * global_lc.size(0)
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

        final_train_loss = epoch_loss / total
        final_train_accuracy = correct / total
        print(f"Epoch {epoch+1}/{num_epochs} - Train Loss: {final_train_loss:.4f} - Train Accuracy: {final_train_accuracy:.2%}")

    test_metrics = evaluate(model, test_loader)
    print(f"\nHeld-out real-star test accuracy: {test_metrics['accuracy']:.2%} (n={test_metrics['n']})")
    print("Per-class held-out accuracy:", test_metrics["per_class_accuracy"])

    weights_dir = os.path.dirname(os.path.abspath(__file__))
    weights_path = os.path.join(weights_dir, "model_weights.pth")
    torch.save({
        "state_dict": model.state_dict(),
        "architecture_version": DL_ARCHITECTURE_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "num_epochs": num_epochs,
        "final_train_accuracy": final_train_accuracy,
        "final_train_loss": final_train_loss,
        "test_accuracy": test_metrics["accuracy"],
        "training_data": "real_kepler_lightcurves+real_koi_disposition_labels; centroid branch honestly zeroed/absent (no real Kepler TPF centroid in this pass)",
        "num_samples": len(train_data),
        "num_real_stars": n_stars,
    }, weights_path)
    print(f"Saved model weights to {weights_path} (architecture_version={DL_ARCHITECTURE_VERSION}).")

    report_path = os.path.join(weights_dir, "dl_training_report.json")
    report = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "architecture_version": DL_ARCHITECTURE_VERSION,
        "class_names": CLASS_NAMES,
        "num_real_stars": n_stars,
        "real_star_class_distribution": {CLASS_NAMES[c]: int(np.sum(star_labels == c)) for c in range(len(CLASS_NAMES))},
        "num_epochs": num_epochs,
        "train_samples": len(train_data),
        "held_out_test_samples": len(test_data),
        "held_out_test_stars": len(test_star_idx),
        "final_train_accuracy": final_train_accuracy,
        "final_train_loss": final_train_loss,
        "held_out_test_metrics": test_metrics,
        "data_source": (
            "NASA Exoplanet Archive cumulative KOI table (real disposition + real "
            "false-positive-reason flags) + real Kepler long-cadence light curves via "
            "lightkurve/MAST. No synthetic light curves in this training set."
        ),
        "known_gaps": (
            "Centroid branch honestly zeroed/absent for every sample (no real Kepler "
            "TPF centroid ingestion in this pass). Metadata vector uses only real "
            "koi_steff/koi_srad/koi_depth; no 2MASS/Pan-STARRS/RUWE cross-match "
            "attempted for these Kepler stars, so those fields are honestly absent "
            "(presence=0), not fabricated."
        ),
    }
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote training report to {report_path}")


if __name__ == "__main__":
    train_model()
