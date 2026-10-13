# Phase B: Temporal Validation Report
This report evaluates the model's predictive performance on candidates discovered *after* a specific year, using a model trained *only* on candidates discovered *before* that year.

## Temporal Split Performance Matrix

| Training Cutoff | Test Epoch | Train Size | Test Size | ROC-AUC | PR-AUC | Accuracy | F1-Score | Brier (Calibration) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Pre-2020 | 2020 to Present | 1080 | 1587 | 0.8563 | 0.8466 | 0.7795 | 0.7934 | 0.1533 |
| Pre-2021 | 2021 to Present | 1530 | 1137 | 0.8391 | 0.8288 | 0.7590 | 0.7728 | 0.1635 |
| Pre-2022 | 2022 to Present | 2152 | 515 | 0.8521 | 0.9058 | 0.7495 | 0.7861 | 0.1609 |
| Pre-2023 | 2023 to Present | 2425 | 242 | 0.8690 | 0.9076 | 0.7686 | 0.8028 | 0.1495 |
| Pre-2024 | 2024 to Present | 2536 | 131 | 0.8720 | 0.9210 | 0.7634 | 0.8050 | 0.1488 |

## Temporal Validation Analysis (computed from the table above)
*   **ROC-AUC range:** 0.839 to 0.872 across cutoffs (mean 0.858); 0 of 5 cutoffs exceed 0.90.
*   **Brier score:** 0.149 to 0.164; 2 of 5 cutoffs are below 0.15. The 0.25 reference is an uninformative constant prediction.
*   **Interpretation:** performance on later TOIs is materially lower than the random-split headline (AUC ~0.93). See `backend/app/ml/honest_evaluation_report.json` for star-grouped and time-forward evaluation with confidence intervals and a TOI-table-only baseline.
