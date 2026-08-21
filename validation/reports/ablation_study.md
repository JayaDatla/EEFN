# Phase C: Feature Ablation Study
This study evaluates the relative contribution of different categories of features to check if the evidence-fusion parameters improve exoplanet validation performance.

## Model Ablation Performance Comparison (5-Fold CV)

| Model Configuration | Mean ROC-AUC | Mean Accuracy | Mean F1-Score | Delta (vs Baseline) |
| :--- | :--- | :--- | :--- | :--- |
| Model A: Baseline TESS Only | 0.9137 | 0.8343 | 0.8365 | +0.0000 |
| Model B: Gaia Only | 0.8228 | 0.7357 | 0.7337 | -0.0910 |
| Model C: Conflict Features Only | 0.7491 | 0.6693 | 0.6764 | -0.1646 |
| Model D: Agreement Features Only | 0.7477 | 0.6847 | 0.6660 | -0.1661 |
| Model E: All Evidence Fusion | 0.9177 | 0.8436 | 0.8442 | +0.0040 |

## Feature Importance Readout (All Features)
Here are the top 15 most important features in the combined model:

```text
            feature  importance
           pl_insol    0.074685
             pl_eqt    0.072071
         pl_trandep    0.062360
            st_logg    0.059478
             st_rad    0.058036
            pl_rade    0.056194
               RUWE    0.056066
        pl_trandurh    0.053111
            st_dist    0.053079
    derived_rp_gaia    0.050266
          pl_orbper    0.047474
derived_rp_diff_rel    0.041868
            st_teff    0.041787
    derived_rp_diff    0.039984
          dist_diff    0.033787
```

## Performance Deltas & Key Insights
*   **Value of Fusion:** Model E (All Features) outperforms the baseline TESS parameters (Model A) by **+0.0040** in ROC-AUC.
*   **Conflict Metrics Power:** Model C (Conflict Features Only) achieves an ROC-AUC of **0.7491**, demonstrating that disagreement alone carries strong physical signatures.
