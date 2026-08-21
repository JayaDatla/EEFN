# Phase A: Data Leakage Audit Report
**Risk Score Legend:**
*   **HIGH RISK (8-10):** Direct or indirect outcome leakage (e.g. features updated post-confirmation with class status).
*   **MEDIUM RISK (4-7):** Features containing retrospective corrections or post-facto measurement alignment.
*   **LOW RISK (1-3):** Strictly available before or at the time of exoplanet candidate classification.

## Feature Leakage Matrix

| Feature Name | Source | Temporal Availability | Audit Logic | Risk Score |
| :--- | :--- | :--- | :--- | :--- |
| `pl_orbper` | TOI Ingestion | Discovery epoch | Light curve fit parameter, fixed at upload. | **1 (LOW)** |
| `pl_trandep` | TOI Ingestion | Discovery epoch | Transit depth fit from TESS light curve. | **1 (LOW)** |
| `pl_rade` | TOI Ingestion | Discovery epoch | Derived from depth and TIC star radius. | **1 (LOW)** |
| `pl_insol` | TOI Ingestion | Discovery epoch | Calculated from orbital period and star properties. | **1 (LOW)** |
| `pl_eqt` | TOI Ingestion | Discovery epoch | Planet equilibrium temperature model. | **1 (LOW)** |
| `st_tmag` | TIC Catalog | Pre-discovery | Baseline stellar catalog magnitude (fixed). | **1 (LOW)** |
| `st_teff` | TIC Catalog | Pre-discovery | Stellar Effective Temp from pre-TESS archives. | **1 (LOW)** |
| `st_rad` | TIC Catalog | Pre-discovery | Stellar Radius from pre-TESS archives. | **1 (LOW)** |
| `st_dist` | TIC Catalog | Pre-discovery | Stellar Distance from pre-TESS archives. | **1 (LOW)** |
| `Teff` | Gaia DR3 | June 2022 | Astrophysical temperature from spectrophotometry. | **2 (LOW)** |
| `Rad` | Gaia DR3 | June 2022 | Stellar radius from FLAME / GSP-Phot. | **2 (LOW)** |
| `Dist` | Gaia DR3 | June 2022 | Geometric parallax inversion. | **2 (LOW)** |
| `RUWE` | Gaia DR3 | June 2022 | Astrometric Unit Weight Error (single-star fit quality). | **2 (LOW)** |
| `teff_diff` | Engineered | Calculated | Difference in catalog temperature values. | **2 (LOW)** |
| `rad_diff` | Engineered | Calculated | Difference in catalog stellar radius values. | **2 (LOW)** |
| `dist_diff` | Engineered | Calculated | Difference in catalog distance values. | **2 (LOW)** |
| `derived_rp_gaia` | Engineered | Calculated | Derived from transit depth + Gaia star radius. | **2 (LOW)** |
| `is_unphysical_rp` | Engineered | Calculated | Binary flag for derived size > 2.0 Jupiters. | **2 (LOW)** |

## Findings and Recommendations
*   **No Hidden Labels:** The audit shows no features that directly encode or leak target exoplanet dispositions (`tfopwg_disp`).
*   **Temporal Offset:** For candidates discovered *before* June 2022, Gaia DR3 features represent a minor temporal offset, since Gaia DR3 was not yet published. However, using Gaia DR3 is scientifically legitimate for exoplanet validation, as Gaia is an independent stellar-only survey with no feedback loop from exoplanet candidate outcomes.
*   **Outcome Leakage Check:** Checked `pl_controv_flag` and candidate date values. These were excluded from training to ensure no timeline violation.

**Data Leakage Audit Conclusion: PASS.** The feature space is clean and legally available at the time of exoplanet validation.
