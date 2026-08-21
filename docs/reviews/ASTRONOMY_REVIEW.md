# Board A: Astronomy Peer Review Panel Evaluation

**Review Panel Roles**:
*   Senior Exoplanet Scientist (Chair)
*   Gaia DR3 Astrophysical Parameters Specialist
*   Astronomy & Computing Reviewer
*   Nature Astronomy Peer Reviewer
*   ADASS Program Committee Member

---

## 1. Executive Summary
The Exoplanet Evidence Fusion Network (EEFN) attempts to resolve the entity cross-matching and planetary parameter reconciliation problem between the TESS Input Catalog (TIC) / NASA Exoplanet Archive and the Gaia DR3 dataset. While the concept of modeling cross-catalog disagreement as a feature for planetary confirmation is interesting, the manuscript suffers from significant methodology overclaims, circular reasoning, and simplifications that make it unsuitable for publication in high-impact journals in its current form.

---

## 2. Peer Review Criticisms

### Criticism 1: Trivialization of Stellar Property Discrepancies
*   **Severity**: **HIGH**
*   **Confidence**: 95%
*   **Evidence**: The model treats simple numerical differences (e.g. `teff_diff`, `rad_diff`) between the TIC and Gaia DR3 catalogs as high-importance features for "planet confirmation probability."
*   **Why it matters**: Catalog disagreement in stellar parameters ($T_{eff}$, $R_*$) is a well-known consequence of different evolutionary track models and spectral bands used by the TESS and Gaia pipelines. It does *not* directly indicate the physical existence or non-existence of an orbiting planet candidate. Conflating catalog disagreement with planetary confirmation probability is scientifically misleading.
*   **Proposed fix**: Reframe the ML task. The model should predict the probability that a target's stellar parameters are *contaminated by a stellar binary* (a true false-positive trigger) rather than a general "planet confirmation probability."
*   **Publication Blocker?**: **YES**

---

### Criticism 2: Overclaimed Novelty of "Evidence Fusion"
*   **Severity**: **MEDIUM**
*   **Confidence**: 90%
*   **Evidence**: The authors present "cross-catalog evidence fusion" as a breakthrough methodology.
*   **Why it matters**: Cross-matching catalogs (e.g., using CDS XMatch) and calculating derived physical parameters is a standard, everyday practice in exoplanet curation (e.g., ExoFOP, NASA Exoplanet Archive pipelines). Using random forests on these differences is incremental, not a paradigm shift.
*   **Proposed fix**: Temper the language. Focus on the automated scaling and unified alert classification rather than marketing "fusion" as a novel scientific mechanism.
*   **Publication Blocker?**: **NO**

---

### Criticism 3: Albedo Simplification in Equilibrium Temperature
*   **Severity**: **MEDIUM**
*   **Confidence**: 100%
*   **Evidence**: The system assumes a fixed Bond Albedo of zero ($A_B = 0$) for all equilibrium temperature calculations.
*   **Why it matters**: Real exoplanetary equilibrium temperatures are sensitive to albedo and atmospheric redistribution assumptions. A fixed albedo of zero represents an upper limit, not a realistic physical temperature.
*   **Proposed fix**: Explicitly state that $T_{eq}$ calculations represent the $A_B = 0$ blackbody limit, and include a footnote detailing how varying albedo (e.g., $A_B = 0.3$) shifts the temperature scale.
*   **Publication Blocker?**: **NO**

---

### Criticism 4: Circular Data Dependency in validation_dataset
*   **Severity**: **HIGH**
*   **Confidence**: 85%
*   **Evidence**: The training target label (`tfopwg_disp`) mapped to `CP/KP` (Confirmed Planet) and `FP/FA` (False Positive) is derived from campaigns that used Gaia parameters retrospectively to vet candidates.
*   **Why it matters**: If astronomers used Gaia DR3 distances and RUWE to flag a candidate as a false-positive binary, and those same Gaia parameters are fed as training features to the Random Forest model, the model is simply learning the decision rules of the astronomers who labeled the dataset. This represents a form of target leakage/circularity.
*   **Proposed fix**: Perform an ablation study showing model performance on candidates labeled *before* the release of Gaia DR3 parameters.
*   **Publication Blocker?**: **YES**

---

## 3. Panel Answers to Key Questions

*   **Does EEFN contribute new scientific knowledge?**
    No. It automates catalog cross-vetting and flags anomalies, but it does not reveal new physical laws or discover new planets.
*   **Is evidence fusion genuinely novel?**
    No. It is a standard data engineering merge combined with a Random Forest classifier.
*   **Is disagreement modeling scientifically meaningful?**
    Yes, but only as a diagnostic proxy for binary blends, not as a direct planetary physics parameter.
*   **Are impact claims justified?**
    Partially. Avoided telescope hours assume that astronomers would have blind-allocated time to obvious false positives, which is historically untrue as manual vetting exists.
*   **What would cause rejection?**
    The circular logic in feature-to-label correlation (Criticism 4) and the overclaims of "planet confirmation" would trigger a immediate rejection from Nature Astronomy or ApJ.

---
*Status: REJECT IN CURRENT FORM (Major Revision Required)*
