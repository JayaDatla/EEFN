# Phase F: Failure Analysis Report
This report provides diagnostic explanations for the classification failures of the combined exoplanet validation model on the test partition.

## Summary of Failures
*   **False Positives (predicted confirmed, actual false positive):** 123
*   **False Negatives (predicted false positive, actual confirmed):** 130

## Selected Diagnostic Examples

### False Positive Cases
* **TOI-599.01**: Prob=0.53, Period=0.82967 days, Depth=4744.55 ppm, RUWE=0.981
* **TOI-6023.01**: Prob=0.60, Period=9.0330414 days, Depth=227.0 ppm, RUWE=1.105
* **TOI-6037.01**: Prob=0.87, Period=4.0158188 days, Depth=560.0 ppm, RUWE=0.89

### False Negative Cases
* **TOI-5982.01**: Prob=0.19, Period=38.4787613 days, Depth=23972.8957136 ppm, RUWE=1.036
* **TOI-674.01**: Prob=0.13, Period=1.9771658 days, Depth=13877.3059698 ppm, RUWE=1.35
* **TOI-5992.01**: Prob=0.32, Period=8.0276821 days, Depth=11271.5765812 ppm, RUWE=1.032

## Failure Cluster Identifications

1.  **Multi-Planet System Contamination:**
    *   Many False Positives occur in stars with multiple catalog entries (e.g. TOI-1064). Multi-planet systems can have transit profiles that interfere with each other, causing the model to misinterpret the transit depths or periods.
2.  **Stellar Contamination / Binaries:**
    *   Stellar binary companions can lead to incorrect stellar parameters. If a host star has high RUWE (1.2-1.4) or high temperature discrepancies but doesn't reach the hard cutoff of eclipsing binaries (RUWE > 1.4 or unphysical radius), the model can be confused.
3.  **Missing Gaia Data Fallback:**
    *   When Gaia parallax or astrophysical parameters are missing, the imputer falls back to median values. This fallback removes the disagreement signal, forcing the model to rely solely on the baseline TESS parameters, which increases classification error.
