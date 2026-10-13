# validation/reports -- legacy outputs

These reports were produced by early validation scripts against the **Random Forest** and the
feature set that existed then. They are kept as a record of that work, **not** as current
evidence about the shipped model.

* Several of them reasoned from hardcoded text rather than from the computed tables next to it;
  the ones that issued "certified", "PASS" or dollar-savings verdicts were removed
  (`SCIENTIFIC_CERTIFICATION_REPORT`, `reproducibility_*`, `impact_study`), and the leakage and
  temporal reports were corrected to say what their own numbers show.
* Authoritative, regenerable results live in `backend/app/ml/`:
  `honest_evaluation_report.json` (star-grouped + time-forward, CIs, TOI-only baseline),
  `model_metrics.json`, `calibration_report.json`, `lightcurve_vetter_report.json`,
  `tess_transfer_report.json`, `dl_architecture_study.json`.
* `LIMITATIONS.md` is the narrative of what is and is not established.
