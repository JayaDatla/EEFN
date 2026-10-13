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
| `st_teff` | TIC Catalog | Pre-discovery | Teff derived by TIC-8 from Gaia DR2 colours (Stassun+2019) -- not independent of Gaia. | **1 (LOW)** |
| `st_rad` | TIC Catalog | Pre-discovery | Radius derived by TIC-8 from Gaia DR2 parallax + photometry (Stassun+2019) -- not independent of Gaia. | **1 (LOW)** |
| `st_dist` | TIC Catalog | Pre-discovery | Distance from Gaia DR2 parallax (Bailer-Jones+2018) in TIC-8 -- not independent of Gaia. | **1 (LOW)** |
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
*   **This is NOT a clean pass.** The earlier version of this report certified the feature space as "clean" and concluded PASS. That conclusion was not supported:
*   **Label circularity is untested here.** `tfopwg_disp` dispositions were assigned by human reviewers who used the same kinds of signals the features encode (Gaia RUWE/parallax/radius, the SPOC transit depth and radius). The two ablations in LIMITATIONS.md section 1.1 are weak proxies (pre/post-EDR3 re-splits; an RV-confirmed holdout of positives only). A negative-side clean-label test does not exist.
*   **The TOI-table stellar values are derived from Gaia** (TIC-8 uses Gaia DR2), so TOI-minus-Gaia differences are not independent evidence. See `backend/app/ml/honest_evaluation_report.json`: the cross-catalog features add only ~+0.008 AUC over the TOI-table columns alone under star-grouped CV, and nothing under time-forward splits.
*   **No target columns are used as features** (`tfopwg_disp` and `pl_controv_flag` are excluded), which rules out direct label leakage only.
*   **Temporal offset:** Gaia DR3 (June 2022) postdates most TOI dispositions; it is a feature at serving time, not at the time most labels were assigned.

**Data Leakage Audit Conclusion: NOT ESTABLISHED.** Direct label leakage was excluded; circularity through shared signals was not, and cannot be with the available labels.
