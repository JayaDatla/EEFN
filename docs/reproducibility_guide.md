# EEFN Reproducibility Guide

What can be reproduced exactly, what needs network access, and what cannot be reproduced from this
repository alone. Nothing here is certified; each step says how to check it yourself.

---

## 1. Environment
Python 3.11+ with the pinned versions in `backend/requirements.txt` (a pickled model is only safe
across identical `scikit-learn==1.9.1` / `lightgbm==4.7.0`; both versions are recorded in
`backend/app/ml/model_metrics.json` and the loader warns on a mismatch).
```bash
cd backend && pip install -r requirements.txt
```

## 2. Reproduce the published tabular-model metrics (offline, ~10 s)
```bash
python reproduce_results.py
```
Recomputes the dataset hash and the held-out accuracy / ROC-AUC / F1 / Brier from the frozen input
`validation/data/validation_dataset.csv` (same split, same seed, same parameters) and **exits
non-zero if any value differs from `model_metrics.json` / `calibration_report.json` by more than
0.002**. It writes nothing and prints no verdict it did not compute.

## 3. Regenerate the model and its evaluation (offline)
```bash
python validation/scripts/train_and_serialize_model.py        # model + model_metrics.json + calibration_report.json
python backend/validation/scripts/honest_evaluation.py        # star-grouped + time-forward + TOI-only baseline + CIs
python validation/scripts/leakage_ablation.py                 # pre/post-EDR3 probe (weak proxy, see LIMITATIONS 1.1)
```
`honest_evaluation.py` is the evaluation to quote: the random-split numbers in `model_metrics.json`
are the most favourable protocol.

## 4. What needs network access (hours, not seconds)
* `validation/scripts/augment_dataset_photometry.py` -- CDS X-Match of 2MASS / Pan-STARRS onto the CSV
  (already applied to the committed CSV).
* `backend/validation/scripts/fetch_real_kepler_dataset.py` -- real Kepler light curves from MAST
  (~60-90 s per star, throttled; the raw cache is untracked).
* `backend/validation/scripts/train_lightcurve_vetter.py`, `dl_architecture_study.py`,
  `tess_transfer_check.py` -- train and evaluate the light-curve vetter; the transfer check
  downloads real SPOC light curves and depends on the NASA Exoplanet Archive being reachable.

## 5. What cannot be reproduced from this repository
* **The script that built `validation_dataset.csv`.** The CSV (TOI table + Gaia DR3 cross-match +
  dates) is a frozen input; its SHA-256 prefix is recorded in `model_metrics.json`. The code that
  originally produced it was not kept. `augment_dataset_photometry.py` only adds the 2MASS /
  Pan-STARRS columns.
* **Archive contents over time.** The NASA Exoplanet Archive and Gaia are living catalogs; a fresh
  download will differ from the frozen CSV.
* **`validation/reports/*`** are legacy outputs of early scripts (see the README there), not
  current evidence.
