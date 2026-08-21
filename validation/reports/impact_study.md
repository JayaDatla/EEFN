# EEFN Historical Ingest & Operational Impact Study

This study quantifies the retrospective operational impact of the **Exoplanet Evidence Fusion Network (EEFN)**. It asks: *If EEFN had existed historically, how many false-positive follow-up efforts could have been avoided by flagging catalog discrepancies earlier?*

---

## 1. Historical Dataset Summary
*   **Sample Size:** 2,667 resolved TESS Objects of Interest (TOIs)
*   **Actual Confirmed Planets (CP/KP):** 1,323 (49.6%)
*   **Actual False Positives (FP/FA):** 1,344 (50.4%)
*   **Epoch Coverage:** 2018 – 2026

---

## 2. Alert Effectiveness Metrics

The table below evaluates the precision, recall, and false alert rate for each rule-driven alert type in flagging actual False Positive candidates:

| Alert Type | Triggered Alerts | True Alerts (TP) | False Alerts (FP) | Precision (Quality) | Recall (Coverage) | False Alert Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Unphysical Derived Planet Size (>22 Re)** | 102 | 91 | 11 | 0.8922 | 0.0677 | 0.0083 |
| **Gaia RUWE Anomaly (>1.4)** | 396 | 322 | 74 | 0.8131 | 0.2396 | 0.0559 |
| **Stellar Temperature Mismatch (>500K)** | 177 | 152 | 25 | 0.8588 | 0.1131 | 0.0189 |
| **Combined Quality Alerts** | 576 | 473 | 103 | 0.8212 | 0.3519 | 0.0779 |

### Analysis of Metrics:
*   **Derived Planet Radius Precision:** Achieving **89.22%** precision shows that when the derived planet radius is unphysically large, it is almost certainly a stellar binary (FP). Only a tiny fraction of confirmed planets trigger this alert, representing low false alert risk.
*   **Gaia RUWE Coverage:** Gaia RUWE anomaly flags **322** false positives with **81.31%** precision. This confirms that astrometric noise is a highly clean indicator of binary companions.
*   **Combined Alerts:** Triggering any of the three alerts yields **473** correct flags out of **576** total alerts, with a combined precision of **82.12%** and a false alert rate of **7.79%**.

---

## 3. Resource Allocation & Operational Savings

By automatically flagging these conflicts, EEFN would have avoided ground-based follow-up campaigns for the verified false positives:

*   **False Positive Candidates Avoided:** 473 targets
*   **Telescope Observations Avoided:** 1419 observations *(Assuming 3 observations avoided per target: speckle imaging, recon spectroscopy, and transit photometry)*
*   **Estimated Follow-up Telescope Hours Saved:** 5676 hours *(Assuming an average of 12 hours of telescope and calibration time per target)*
*   **Estimated Financial Savings:** $709,500 USD *(Assuming a conservative operational cost of $1,500 equivalent per telescope night)*

---

## 4. Failure Cases & Scientific Limitations
*   **False Negative Failures (Missing alerts on FPs):** The combined alerts only have a recall of **35.19%**, meaning that **871 false positives** were *not* caught by these three simple rules. These represent false positives caused by other phenomena (e.g. background eclipsing binaries in the same pixel, instrumental systematics) which do not alter the host star's radius or RUWE.
*   **Historical Timeline Mismatch:** For targets discovered before 2022, Gaia DR3 was not yet published. In a true historical simulation, we would have had to fall back to Gaia DR2 or EDR3, which had slightly lower precision and coverage.

---

## 5. Summary Recommendations
1.  **Integrate alerts directly into target selection pipelines** for the TESS Follow-up Observing Program (TFOP).
2.  **Enforce a strict filter on derived planet radius** prior to requesting high-resolution spectroscopy.
