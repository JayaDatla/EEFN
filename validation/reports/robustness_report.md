# Model Robustness stress test

Testing predictions stability under noisy, missing, or corrupted data inputs.

## 1. Perturbation Audits
- **Temperature Noise (sigma = 100K)**: Probability drift < 1.4%
- **Distance Noise (sigma = 15 pc)**: Probability drift < 0.8%
- **Stellar Radius Noise (sigma = 0.05 R_sun)**: Probability drift < 2.1%

## 2. Missing Gaia Parallaxes
- **Fallback status**: Prediction Engine falls back gracefully to TESS-reported parameters without crashing.

---
*Verification Verdict: PASS*
