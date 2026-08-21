# EEFN Scientific Reproducibility Guide

This guide describes how to replicate all dataset generations, features engineering, model training, evaluation metrics, and validation summaries for the Exoplanet Evidence Fusion Network (EEFN) platform.

---

## 1. Prerequisites & Environment
Ensure you have Python 3.11+ installed along with the required scientific libraries:
```bash
pip install pandas numpy scikit-learn requests matplotlib
```

---

## 2. One-Command Replication
All steps of the scientific validation studies are automated under a single runner script:
```bash
python reproduce_results.py
```

### Steps executed by the runner:
1.  **`prepare_validation_data.py`:**
    *   Downloads raw exoplanet candidate date fields (`toi_created`, `rowupdate`, `release_date`) from the NASA Table Access Protocol (TAP) service.
    *   Merges dates with the cached local Gaia DR3 cross-matches, saving the clean dataset to `validation/validation_dataset.csv`.
2.  **`run_validation_suite.py`:**
    *   **Data Leakage Audit:** Reviews features and outputs threat risk scores.
    *   **Temporal Validation:** Runs Random Forest classifiers across multiple time-based train-test splits.
    *   **Feature Ablation:** Trains baseline, Gaia-only, conflict-only, and combined models, recording cross-validation scores.
    *   **RUWE Dominance:** Runs evaluations with and without the Gaia RUWE indicator.
    *   **Bootstrap Significance:** Runs 500 bootstrap resamples on predictions to compute the 95% confidence interval of improvement.
    *   **Failure Analysis:** Isolates classification failures and groups them into physical failure clusters.
3.  **Outputs:**
    *   Generates all markdown audit reports inside the `validation/` directory.
