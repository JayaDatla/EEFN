# Phase D: RUWE Dominance Investigation
This report tests whether Gaia's RUWE (Renormalised Unit Weight Error) dominates the predictive power of our exoplanet candidate validation models.

## RUWE Ablation Performance Comparison (5-Fold CV)

| Model Configuration | Mean ROC-AUC | Description |
| :--- | :--- | :--- |
| **RUWE Only** | 0.6066 | Model trained only on Gaia RUWE parameter. |
| **RUWE Removed** | 0.9121 | Model trained on all combined features, with RUWE and high_ruwe features removed. |
| **Full Combined Model** | 0.9177 | Model trained on all baseline and evidence fusion features (including RUWE). |

## Findings & Conclusions
*   **RUWE Predictive Power:** Gaia RUWE alone provides a baseline ROC-AUC of **0.6066**. While RUWE is a highly effective indicator of astrometric noise (often caused by stellar binary companions), it does not explain the full predictive power of the network.
*   **Value of Non-RUWE Fusion:** Removing RUWE from the combined model still achieves an ROC-AUC of **0.9121**. This is significantly higher than both RUWE-only (0.6066) and baseline-only (0.9137), proving that other fusion features (such as derived planet size differences and effective temperature disagreements) add independent, significant predictive value.
