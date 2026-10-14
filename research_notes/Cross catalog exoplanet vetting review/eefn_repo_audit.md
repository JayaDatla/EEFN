# EEFN Repository Audit (D:\Gemini_Projects\EXO): scientific, methodological and engineering mistakes, prior-review status, and value assessment

Audit date 2026-10-13, read-only. Sources are local repo files and artifacts (cited by path/line; there are no web URLs). "Re-computed" means I re-ran analysis in the scratchpad on the committed `validation/data/validation_dataset.csv` (2,667 labelled TOIs, CP/KP=1, FP/FA=0) using the repo's own `build_features` and `LGBM_PARAMS`, with no repo file modified. My re-computation reproduced the shipped held-out numbers exactly (AUC 0.9267, acc 0.8539, Brier 0.1003), so the reproduction is trustworthy. Local DB snapshot: `backend/eefn.db`, opened read-only, untracked by git.

## Key question 1. What mistakes, contradictions and overclaims exist (A), ranked by severity

### Takeaway
The most serious defect is a train/serve skew: the served LightGBM score never sees any cross-catalog disagreement, because `HostStar` stores only Gaia values and `predict.py` copies them into both the "TOI" and "Gaia" slots. Separately, the cross-catalog features add only about +0.008 ROC-AUC over TOI-table columns alone, and under a temporal split the headline 0.927 AUC falls to about 0.85. Sibling-TOI leakage is real but negligible (a null result worth stating). Several stale "PASS" reports and hardcoded report text still contradict the honest LIMITATIONS.md.

### Cited Findings (verified)

**A1. CRITICAL: served score has all disagreement features identically zero or missing (train/serve skew).**
- `backend/app/ml/predict.py` lines ~58-66 and ~215-232: `st_teff`, `Teff` are both set to `host_obj.teff`; `st_rad`/`Rad` to `host_obj.rad`; `st_dist`/`Dist` to `host_obj.distance`. `_extract_raw_inputs` also falls back `Teff = data.get("Teff", st_teff)`.
- `backend/app/pipeline/ingest.py` lines ~339-346 store only Gaia values on the host (`star.teff = row['Teff']`, `star.rad = row['Rad']`, `star.distance = row['Dist']`). The TOI/TIC `st_teff/st_rad/st_dist` are used only transiently for `AgreementMetrics` and the health score (lines ~376-450) and are never persisted on the host.
- The test enshrines it: `backend/tests/test_predict.py:109` asserts `row["teff_diff"] == 0.0  # Teff falls back to st_teff`.
- Measured on the live DB (546 candidates, read-only): `teff_diff`, `rad_diff`, `dist_diff` are 0 for all 440 candidates that have Gaia astro-params and None for the other 106. Zero non-zero values. Completeness feature takes only values {0:12, 1:94, 7:440}, whereas training has values 4 (n=412) and 7 (n=2077) dominant.
- Consequence for the 19.4% of hosts (106/546) lacking Gaia astro-params: the served `st_teff/st_rad/st_logg/st_dist` are NaN (training had TIC values for 98% of rows) and `completeness`=1 (a value that in training means almost-everything-missing, label rate 0.0). Mean served score for those 106 is 0.12 vs 0.50 for the rest.
- Re-computed effect (train-style model, test split rebuilt to serving conventions): AUC 0.9267 to 0.9005, accuracy 0.854 to 0.807, Brier 0.100 to 0.137. On the Gaia-AP-missing subset (n=102 of 534): accuracy 0.833 to 0.647, mean predicted 0.34 to 0.12 against a true positive rate of 0.37.
- Corroboration: the production model's in-sample AUC on its own training CSV is 0.994, but on the same kind of rows scored through the serving path (DB rows with CP/KP/FP/FA labels) it is about 0.92, close to the held-out figure.
- Not documented anywhere: LIMITATIONS.md item 3 describes a different train/serve skew (tmag, fixed) and item 8(2) mentions APOGEE substitution, but not this. README, DATA_FLOW.md (lines 289-309 show a worked `teff_diff` example of 50 K) and the frontend `data-pipeline/page.tsx` (RF_FEATURES list "TOI vs. Gaia disagreement") all describe disagreement features that production does not supply.
- Stored scores are also stale: `ml_predictions.calculated_at` for the 500 real rows ends 2026-08-20, before the 2026-10-11 LightGBM retrain; `MLPrediction` has no `model_version` column, so served scores cannot be tied to a model. (Local dev DB only; production state unknown.)

**A2. HIGH: "cross-catalog" features add almost nothing; the score mostly reproduces TFOP dispositions from TOI-table columns.** Repeated StratifiedGroupKFold(5) by TIC, 5 seeds, re-computed:

| Feature set | ROC-AUC | Accuracy |
|---|---|---|
| Full 27 features (shipped) | 0.9232 +/- 0.002 | 0.851 |
| TOI-table only (period, duration, depth, Rp, insol, Teq, st_teff/rad/logg/dist) | 0.9153 +/- 0.002 | 0.842 |
| Full minus RUWE/high_ruwe | 0.9207 | 0.847 |
| Planet-only columns (no stellar) | 0.900 | 0.826 |
| Disagreement-type features only | 0.798 | 0.736 |
| RUWE only | 0.598 | 0.572 |
| Logistic on 8 log TOI features | 0.764 | 0.691 |
- Cross-catalog + Gaia features add about +0.008 AUC (+0.9 points accuracy). The project's own earlier ablation says the same: `validation/reports/ablation_study.md` Model A (TESS only) 0.9137 vs Model E (all) 0.9177, delta +0.0040; `reproduce_results.py` itself prints baseline 0.9137 vs combined 0.9154. The README and showcase page nonetheless present the full-model number.
- Under a temporal split (re-computed with the shipped LightGBM params): train on TOIs created <=2020, test on >=2021 (n=1137): AUC 0.846, accuracy 0.765, Brier 0.169, and the TOI-only model gives an identical AUC 0.846. Train <=2021, test >=2022 (n=515): AUC 0.874, accuracy 0.757. The repo's own `validation/reports/temporal_validation_report.md` (RF) shows the same drop (AUC 0.839-0.872, accuracy 0.75-0.78, Brier 0.149-0.164). The headline 0.927/0.854 is a random split. The positive rate also drifts (0.46 pre-2022 vs 0.64 from 2022), so the calibration claim does not transfer.
- The temporal report's prose is hardcoded in `validation/scripts/run_validation_suite.py` and is false against its own table: it says AUC "maintained above 0.90 for most cutoffs" (none of the five exceed 0.872) and Brier "< 0.15 across all" (four of five are above 0.15). LIMITATIONS.md never mentions the temporal degradation.

**A3. HIGH (partly inference): circularity is not resolved, and the ablations do not address the right question.**
- Evidence that RUWE specifically is not driving the model: RUWE-only AUC 0.598; removing RUWE costs 0.0025 AUC. But the RUWE>1.4 rule alone has label rate 0.187 positive (n=396), i.e. it is a strong rule and humans use it. Dropping all Gaia-derived features costs only 0.008 AUC. Together this means the Gaia-circularity worry is mostly moot, because the model barely uses Gaia; the real circularity is the TOI-table columns (SPOC DV depth/radius, which TFOP uses to disposition). That is untestable with these labels.
- Examples of rule-reproduction: `pl_rade` > 30 R_Earth: 0/31 positive; 4-8 R_Earth: 29% positive; <2 R_Earth: 79% positive (labelled set only).
- The two published ablations (`leakage_ablation_report.json`, `leakage_rv_confirmed_report.json`) use weak proxies. (i) Pre- vs post-EDR3 uses current dispositions and independently re-splits each subset (test n=306 and 228, so AUC CI roughly +/-0.03); the post subset differs in composition (fainter, different positive rate). It also still uses the Random Forest, not the shipped LightGBM. (ii) The RV-confirmed "clean holdout" is 104 matched rows (all positive, base rate 50%, bright and large planets, likely easy); 91.4% recall has Wilson 95% CI about 84-95% and cannot detect false positives. Matching is by host TIC, not by planet, so a sibling TOI at an RV host can be wrongly assumed to be the RV planet (not verified in code).
- The stale `validation/reports/data_leakage_report.md` still says "Gaia is an independent stellar-only survey with no feedback loop" and "PASS", contradicting LIMITATIONS 1.1 and README.

**A4. MEDIUM: TOI-vs-Gaia "disagreement" is largely not independent evidence.**
- TOI `st_*` values are TIC values, which are themselves Gaia-derived. In the CSV: TIC `st_dist` vs `1000/Plx(DR3)` median relative difference 0.8% (IQR 0.3-2.1%); TIC vs Gaia GSP-Phot `Dist` median 1.3%; `st_rad/Rad` median ratio 0.99 (IQR 0.958-1.022); `teff_diff` median 127 K.
- `dist_diff_rel` has Spearman 0.715 with parallax S/N (`e_Plx/Plx`) and 0.289 with Tmag, i.e. it is mostly a faintness/parallax-quality proxy. Its single-feature AUC is 0.665 (inverted, i.e. larger disagreement means more likely FP); within Tmag quartiles the AUC ranges 0.24-0.41 (inverted), so it is not purely a brightness proxy, but it is dominated by parallax quality, which is a data-quality nuisance rather than planet physics.
- Gaia astro-params are missing for 19.3% of the labelled set; missingness is label-informative (35.4% positive when missing vs 53.0% when present), and the model has the `completeness` feature that encodes it (completeness=4 has 42% positive vs 55% for 7). This is a faintness/selection artifact, and under the A1 skew it becomes a score-lowering artifact for 19% of served candidates.
- `docs/reviews/ASTRONOMY_REVIEW.md` Criticism 1 raised exactly this; it was never addressed (the model target remains planet-vs-FP rather than contamination).

**A5. MEDIUM: sibling-TOI split leakage is real but negligible (null result).**
- 2,524 stars, 105 with more than one labelled TOI (248 rows; sizes 2:79, 3:16, 4:8, 5:2). 96 of the 105 multi-TOI stars are all-positive, 4 all-negative, 5 mixed.
- With the shipped split (test_size 0.2, seed 42), 34 of 534 test rows (6.4%) share a star with a training row; sibling-label agreement 94%.
- Star-grouped CV AUC 0.9250/0.9251 vs random-fold 0.9234/0.9263: no difference. Multiplicity itself is a latent label signal (multi-planet systems are rarely FPs) that a grouped split removes, but it is not a measurable inflation here.

**A6. MEDIUM: fabricated/seed/stale data still reaches users from the local DB and some UI.**
- `backend/eefn.db`: 46 seed rows (`TOI-1001.0` ... , `health_score_version` NULL) remain among 546 candidates, with random `evidence_consistency_score` (e.g. 0.94, 0.27) written by `seed_db.py` (random.uniform; `seed_db.py:158-162`), seed health grades (41 of 46 are "A"), and seed centroid shifts. 51 non-real rows carry a non-null `centroid_shift_max`, 9 non-real rows have `has_centroid_dip=1`; 50 hosts carry non-real `teff_spec`/`fe_h`. Two `ORPHANED-test-pollution-*` host rows exist. API paths mostly gate on `centroid_is_real` / `spectroscopy_is_real` (`audit.py`), but the seed candidates and their scores appear in lists and counts. `seed_db.py` also does `Base.metadata.drop_all` unconditionally.
- `ingest.py:~399-400`: when Gaia radius is missing, `calc_rp_gaia` silently becomes the TOI `pl_rade` (or 1.0). Result in the live DB: of 106 hosts with no Gaia radius, 89 (84%) store `derived_rp_diff = 0` ("perfect agreement") and `is_unphysical` is computed from the substitute. The in-code comment says this exact class of bug was fixed for the teff/rad/dist diffs but it persists for the derived radius.
- Health score (`backend/app/science/health.py`) is an unvalidated hand-weighted heuristic (e.g. `teff_disagreement/20`, `rad_disagreement/0.05` caps, `or 0.0` for missing). On 383 labelled live rows its AUC vs the TFOP label is 0.785, but 35.6% of grade-A rows (72 of 202) are labelled false positives. Using the zero-for-missing convention, a candidate with no Gaia match loses only completeness points.
- `frontend/src/app/graph/page.tsx`: hardcoded `targetsData` with invented match confidences (99.9/99.8/99.5) and offsets; disclosed by an "Illustrative example" callout, but still invented numbers.
- `frontend/src/app/data-pipeline/page.tsx` lines 14-49: coverage strings ("546 / 546", "409 / 509", "5 / 546") are hardcoded, not queried.

**A7. MEDIUM: stale docs and UI text contradicting current artifacts.**
- `frontend/src/app/showcase/page.tsx:560-563`: "103 candidates ... 93.2%" vs current report 104 candidates / 91.35% (`leakage_rv_confirmed_report.json`); same page quotes pre/post-EDR3 AUC 0.9399/0.9156 vs current 0.9418/0.9074 (`leakage_ablation_report.json`).
- `data-pipeline/page.tsx` says 2MASS/Pan-STARRS are "DL model only" and "Both models" for others; per LIMITATIONS the CNN is no longer served and the tabular model does use 2MASS/PS. `candidates/[id]/page.tsx:2570-2578` still tells users to see "the DL Model page" for a classifier that is no longer used.
- `backend/app/science/tiers.py` docstring/tier names still say RF tabular / Global+Local CNN / "4-branch net" and state Tier 2/3 are unreachable, although the light-curve vetter and centroid ingestion exist.
- `UPGRADE_PLAN.md` Phase 3 checklist still ticks "TOI-104.01 (a real, 5.43-sigma measured offset) returns dl_centroid_available: true", which LIMITATIONS item 8 retracts (now 1.97 sigma); also "feeds CentroidSpatialCNN" for a model no longer served.
- `validation/reports/SCIENTIFIC_CERTIFICATION_REPORT.md` ("Publication Readiness PASS... Certified ready for peer review", "Approved by Antigravity Scientific Review Board"), `reproducibility_certification.md`, `data_leakage_redteam.md` are self-issued PASS documents that contradict `FINAL_BOARD_VERDICT.md` (MAJOR REVISIONS) and LIMITATIONS. `validation/reports/impact_study.md` still publishes "$709,500 USD" and "5676 hours saved" (assumes 3 observations and 12 h per avoided target) although LIMITATIONS 3.3 calls these overclaimed.
- `LIMITATIONS.md` header still says "Status: For Journal Submission and Review" and "Senior Research Team".

**A8. MEDIUM: reproducibility is partial.**
- `reproduce_results.py` runs the suite but then writes a fixed string report (`reproducibility_report.md`) with hardcoded numbers (0.9154, 0.9137, CI [0.0001, 0.0035], "p-value 0.0000", "PASS") regardless of what the suite computed. `docs/reproducibility_guide.md` references a non-existent `prepare_validation_data.py` and `validation/validation_dataset.csv`, and describes only RF/pip packages (no LightGBM). The script that built the base 46-column CSV (TOI + Gaia) is not in the repo; only `augment_dataset_photometry.py` (adds 2MASS/PS) exists. The dataset is a frozen snapshot (all rows `release_date` 2026-05-22) with a recorded sha256 prefix, so training is deterministic (seed 42, versions pinned: scikit-learn 1.9.1, lightgbm 4.7.0), but dataset construction is not regenerable.
- Model artifacts (`model_artifacts.pkl`, `lightcurve_vetter.pkl`, `model_weights.pth`) are pickles committed to git; the Kepler/TESS caches needed to retrain the vetter (`backend/validation/data/kepler_lc_cache`, `tess_transfer_cache.json`) are untracked, so the vetter report cannot be reproduced from a clone without about 2 hours of MAST downloads (`real_kepler_dataset_report.json`: 7,420 s). Only the Kepler training set `.npz` and metadata are tracked.
- `train_and_serialize_model.py` metadata note claims the held-out metrics are "a lower bound on the production model's actual accuracy"; this is unjustified (the refit model has no extra independent evidence, and temporal/serving evaluation shows lower, not higher, performance).

**A9. MEDIUM: light-curve vetter evidence is thin, and some claims exceed it.**
- Kepler training: 205 KOIs from 169 stars (100 Confirmed / 66 EB / 39 Not Transit-Like), star-grouped CV 82.9% +/- 5.6 vs 48.8% majority baseline. Labels are Kepler Robovetter flags (`fetch_real_kepler_dataset.py`: Planet = CONFIRMED with no FP flags; EB = ss or co flag; NT = nt flag). The top features (snr, flatness, odd_even_sigma, secondary_sigma) are close to the Robovetter tests that generated the flags, so the model plausibly reproduces Robovetter logic; the Kepler "EB" class includes the centroid flag the model cannot see. (Inference; no ablation shows otherwise.) CANDIDATE-disposition KOIs were excluded, so the training set is the easy, resolved tails.
- TESS transfer (`tess_transfer_report.json`): 50 TOIs (25 planets, 25 non-planets): accuracy 0.76 (Wilson 95% CI 0.63-0.86), AUC 0.81 (Hanley-McNeil approx 0.69-0.93), planet recall 22/25 = 88% (CI 70-96%), non-planet recall 16/25 = 64% (CI 45-80%). 9 of 25 TFOP false positives are called planets. The vetter was iterated (v1.0.0 to v1.1.0) while measuring on the same 50, so the 76% is not a clean test set. The TFOP labels were assigned by humans who used these light curves. No ablation of the three TOI-catalog inputs (`catalog_depth_ppm`, `rstar`, `implied_rp_earth`, `dur_ratio`), which the tabular analysis shows are label-predictive, so some of the transfer signal may come from the catalog depth rather than the light curve (not verified).
- Outputs are uncalibrated; `0.5` threshold is not tuned; the vetter uses the TOI ephemeris (period/epoch/duration) and cannot detect ephemeris errors, and fetches at most 2 sectors.
- Live coverage is tiny: 8 of 546 candidates vetted (`lc_vetting_status='vetted'`), 5 centroid-measured; 5 of 5 centroid-measured targets are TOI-101 to 105 (the lowest-numbered TOIs). At 15 centroids per night the catalog needs over a year (LIMITATIONS item 8 admits this). On the 8 live vetted known planets, 2 were called Eclipsing Binary (LIMITATIONS 7).

**A10. LOW-MEDIUM: engineering details.**
- `ingest.py propagate_proper_motion`: adds `pmRA*dt` to RA in degrees without dividing by cos(dec); `pmRA` from Gaia is mu_alpha*cos(dec). Wrong by 1/cos(dec) at high |dec| for the stored host RA. The cross-match itself uses unpropagated J2000 TOI positions against Gaia 2016 within 5" nearest neighbour (`catalog_registry.py distance_arcsec=5.0`); I checked mismatch via Tmag-vs-Gmag residuals: 28 of 2,660 (1.1%) differ by more than 0.5 mag (their label rate is 3.6% positive, so they are mostly FP-labelled). Low impact, but nearest-neighbour matching without ID or magnitude validation is the risk the Operations review (Board B) flagged for high-PM fields; only 159 of 2,636 stars have PM>200 mas/yr and only 1 of those is a >0.5 mag mismatch.
- Missing values still use median imputation (the project's `UPGRADE_PLAN.md` line 966 checkbox "Missing-data masking in both RF and DL" is explicitly unchecked; LightGBM can handle NaN natively).
- Calibration: Brier 0.1003, ECE (re-computed) 0.043 on 534 samples; 95% bootstrap CI for AUC 0.902-0.949 and accuracy 0.824-0.882. Mid-range bins hold 13-25 samples (0.25 predicted vs 0.41 observed in the 0.2-0.3 bin). No recalibration; no calibration under temporal or serving conditions. `followup_priority_score = evidence x (0.1 if unphysical else 1)` ignores brightness, depth/SNR, observability, ephemeris uncertainty.
- `/transit_pipeline` simulator still exists (`endpoints.py:~835-870`) generating a light curve from catalog values with `seed = toi*100`; the real-data path is separate and disclosed.
- Selection bias (inference): the training set is only resolved dispositions (CP/KP/FP/FA = 2,667); the actual use population is unresolved PC. The positive prior in training (49.6%) is not the PC population prior, so the "probability" is not a PC-population planet probability even if calibrated on the labelled set.
- Tests: 22 test files (about 134 test functions); there is no test that serves a DB-sourced candidate and checks the disagreement features are non-zero, no train-vs-serve feature parity test (`test_predict.py` actually asserts the skew), no temporal-split regression test, no test of the `calc_rp_gaia` fallback. CI (`.github/workflows/ci-cd.yml`) triggers on `main`/`develop` while the working branch is `master`, and does not run ML retraining or the validation scripts. Light-curve and centroid tests rely on synthetic data.

### Inferences
- The project's honesty effort is real (it self-retracted the TOI-104.01 centroid result and the CNN), but it audited claims, not the serving path; the most damaging bug sits in the one place no test compares training and serving.
- If A1 is fixed by persisting TIC values on `HostStar` (or computing diffs in ingestion and passing them), the expected gain is small in AUC terms (about +0.008) but it removes the 19% systematic low-score artifact; the catalog-disagreement value proposition is then still weak under a temporal split (TOI-only equals full).
- A lower-risk framing is that the model is a TOI-table-based dispositional prior, which is useful as a cheap triage prior but is not "cross-catalog evidence".

### Gaps
- Could not verify the production deployment's DB, scores or model version (only the local dev DB snapshot).
- Did not run the frontend, the API server, tests or any retraining; frontend claims were read from source only.
- Could not verify what fraction of the labelled FP/FA dispositions used Gaia RUWE/parallax (no per-TOI vetting provenance exists in the CSV).
- Did not check whether the 104 "RV-confirmed" matches are the RV planet itself or a sibling TOI.
- Did not quantify Kepler-label vs Robovetter-metric circularity for the vetter.

## Key question 2. What did earlier reviews recommend (B), and what is the status in code?

### Takeaway
Of the five board risks, R-2, R-4 and R-5 are essentially done; R-3 is attempted with weak proxies and omits a known temporal degradation; R-1 (adoption), the one rated CRITICAL, is only partially addressed and the E.5 "TFOP-affiliated astronomer" step shows no sign of having been taken.

### Cited Findings
| Item (source) | Recommendation | Status (evidence) |
|---|---|---|
| R-1 CRITICAL (`docs/reviews/FINAL_BOARD_VERDICT.md`) | Integrate into ExoFOP/MAST via structured APIs; avoid standalone dashboard | Partial. VOTable/CSV/JSON export, `/resolve`, webhooks, `eefn` CLI exist (README "Interoperability"). ExoFOP integration explicitly not done ("needs coordination with ExoFOP maintainers"). Still primarily a standalone Next.js dashboard. |
| R-2 HIGH (SQLite locks) | Postgres | Done in code and docker-compose; default `DATABASE_URL` is still SQLite and the only DB found is SQLite (`LIMITATIONS.md` Operational item 2). |
| R-3 HIGH (target leakage) | Pre-Gaia ablation; clean-label holdout | Attempted (two ablations), but see A3: weak proxies, RF-based, positives only; no negative-side clean test; no temporal-degradation disclosure; no grouped CV in headline. Stale "PASS" leakage reports remain. |
| R-4 MEDIUM (blocking BackgroundTasks) | Out-of-process queue | Done: Arq workers + Redis, nightly cron (`worker.py`), token-bucket rate limiter. |
| R-5 MEDIUM (no package) | `pyproject.toml` | Done: `backend/pyproject.toml`, `eefn` CLI (`backend/eefn/cli.py`). Docs site (Sphinx/ReadTheDocs) and JOSS draft not done (`UPGRADE_PLAN.md` lines 1074-1075 unchecked). |
| E.5 outreach (`UPGRADE_PLAN.md:519-523`, README "highest-leverage") | One TFOP-affiliated astronomer using it for a season | No evidence in the repo of any outreach, user, or feedback; README still lists it as the top "next contribution". Not done. |
| E.4 benchmark (`UPGRADE_PLAN.md:512`, `docs/TOOL_COMPARISON.md`) | Empirical comparison vs TRICERATOPS/ExoMiner/AstroNet/Robovetter on a common set; say honestly whether EEFN adds signal | Methodology-only comparison. The cheap empirical step the doc itself describes (correlate EEFN scores with already-published FPP/ExoMiner values for overlapping TOIs; no need to run those tools) is not done. TOOL_COMPARISON text is also stale (still says RF + synthetic-trained DL, EEFN loses AstroNet comparison). |
| Astronomy board Criticism 1 (HIGH, publication blocker) | Reframe as contamination/binary prediction rather than planet probability; do not call it planet confirmation | Partially: field renamed to `evidence_consistency_score` and UI says "not a physical confirmation probability", but the target is still planet-vs-FP, `MLPrediction.prob_planet` still mirrors the score. |
| ML expert attack (verdict section 4) | Show non-linear model beats 1D cuts; median imputation is lazy | Model vs trivial rules: partially shown here (A2: GBM 0.92 AUC vs logistic 0.76), but the real baseline (TOI-only GBM 0.915) was never reported. Imputation unchanged. |
| Operations review (`OPERATIONS_REVIEW.md`) | RUWE/unphysical-radius alerts are CRITICAL; ML probability is "nice to have"; export, don't host | Alert engine exists; priority score is not observability-aware; exports exist. The Board's "idealized savings" critique is acknowledged in LIMITATIONS 3.3 but the $709,500 figure remains in `validation/reports/impact_study.md`. |
| Failure postmortem (`FAILURE_POSTMORTEM.md`) | Avoid portal trap; handle rate limits; abstract catalogs for Gaia DR4; expect ExoFOP to absorb Gaia columns | Rate limiter done; `catalog_registry.py` partial abstraction (hardcoded VizieR column names and ingest SQL remain, so DR4 would still break); portal trap partially open; ExoFOP-overlap risk unaddressed. |
| LIMITATIONS "Future Work" | Negative-side clean-label test; Gaia G per host (+0.7 pt accuracy); native NaN; labelled centroid validation set; difference-image PRF fit; per-catalog rate buckets | None done (each explicitly marked not attempted). |
| UPGRADE_PLAN open boxes | Missing-data masking in RF (line 966), docs site, JOSS draft (1074-1075) | Still unchecked. Plan ticks other boxes that are now stale (A7). |

### Inferences
- The project's own most-repeated "highest leverage" item (a real observer) is the one with zero repo evidence of progress, and every other open item improves internal rigor rather than adoption.
- R-3 is better described as "partially disclosed" than "mitigated": the missing item is the temporal degradation and the lack of independent negatives.

### Gaps
- Cannot see outreach done outside the repo (emails, conversations).
- `git log` has only 10 commits, so history before the squash/cleanup (commit 6576cdc) is unavailable to check when items were closed.

## Key question 3. Which components add observer value today, which are demo-ware, and what is missing for a TFOP observer to trust it? (C and D)

### Takeaway
Defensible value today: the transparent per-candidate provenance/audit trail, the physics sanity checks (unphysical derived radius, RUWE and TOI/Gaia stellar parameter flags, transit-density check), VOTable export, and the honest self-measurement culture. Weakest: the headline LightGBM "evidence-consistency" score (skewed in serving, mostly a TOI-table prior, degrades over time), the health grade, and the dashboard polish. The real-light-curve vetter and real centroid are the most scientifically interesting additions but are barely populated (8 and 5 of 546) and unvalidated for TESS beyond n=50.

### Cited Findings
**C. Strongest components (evidence)**
- Self-measuring honesty: committed metric artifacts with dataset hash, versions, reliability bins; retracted claims (TOI-104.01, CNN). Exact reproduction of the 0.8539/0.9267 held-out numbers is possible from the CSV.
- Rule-type flags: RUWE>1.4 flag has precision 0.81 for FP labels (396 triggers, 74 false) and unphysical derived radius precision 0.89 (102 triggers) per `validation/reports/impact_study.md`. These are tractable, explainable checks (but TFOP already uses RUWE; the Failure Postmortem anticipates ExoFOP absorbing it).
- Centroid methodology redesign (empirical fake-epoch null, implied-offset = shift/depth) is statistically sound in principle and unit-tested; honestly flagged "none of 5 flagged" and no labelled validation set.
- Engineering hygiene: Arq queue, Redis rate limiter, Alembic, Postgres path, pinned deps, VOTable export, resolver, webhooks, error-state fix for silent fabrication.
- Observability module (`science/observability.py`) uses real astropy geometry, but requires `tranmid` and does not propagate epoch uncertainty; overlaps with the existing TESS Transit Finder (not verified here).

**Weakest / demo-ware**
- LightGBM score: A1 (zeros for disagreement; 19% systematically low), A2 (+0.008 AUC over TOI-only; temporal AUC 0.85), A4. Health grades A-F: heuristic; 36% of grade-A are labelled FP; 41 of 46 seed rows get grade A.
- `/transit_pipeline` simulator, 3D galactic visualizer, graph page numbers, `showcase`/`demo`: presentation, not evidence. Board B classified the 3D explorer "UNNECESSARY".
- Light-curve vetter: Kepler-trained, TESS check n=50 with wide CIs, 36% FP-as-planet rate, uncalibrated; centroid: 5 targets; spectroscopy: 2 hosts.

**D. Concrete suggested changes (prioritized)**
1. Fix serving: persist TIC/TOI `st_teff/st_rad/st_dist/st_logg` on the host (or a separate `toi_*` set) and compute `teff_diff/rad_diff/dist_diff` from the two real sources in `predict.py`; replace `calc_rp_gaia = pl_rade or 1.0` with `None`; add a train-vs-serve parity test using one DB-ingested row and the CSV row for the same TOI; delete or invert `test_predict.py:109`; add `model_version` to `MLPrediction`; re-score the DB.
2. Re-evaluate and republish headline numbers with the metric that matches use: star-grouped plus temporal split (train <=2020, test >=2021 and <=2021 vs >=2022), TOI-only baseline next to the full model, and bootstrap CIs. Disclose AUC about 0.85 and +0.008 from cross-catalog features. Then decide honestly whether the score should be marketed as cross-catalog evidence.
3. Switch LightGBM to native NaN; drop `completeness` as a model feature or replace by explicit missing flags; fit isotonic/Platt on a temporal calibration fold; report calibration under the temporal split.
4. Make the model more useful for the actual use case: train and evaluate on contamination-relevant targets, or at least add the PC population (score the 132-4,000 PCs and compare to eventual dispositions in a prospective test: a time-forward evaluation using the nightly snapshots is the strongest possible validity test and costs nothing).
5. Run the E.4 empirical comparison using published TRICERATOPS FPP/ExoMiner scores for overlapping TOIs, and add a negative-side clean test (e.g., TOIs shown FP by ground-based photometry/spectroscopy).
6. Clean the data: purge the 46 seed rows and 2 orphan hosts from any shared DB, set `centroid_shift_max`/`teff_spec` NULL for non-real rows, make `seed_db.py` require an explicit flag instead of `drop_all`.
7. Delete or relabel stale artifacts: `validation/reports/*` PASS certifications, `impact_study.md` dollar figures, hardcoded text in `run_validation_suite.py` and `reproduce_results.py`; fix `showcase`, `data-pipeline`, `tiers.py`, `UPGRADE_PLAN.md` TOI-104.01 checkbox, `TOOL_COMPARISON.md`, `reproducibility_guide.md`; auto-generate UI numbers from the JSON artifacts instead of typing them.
8. Vetter: add TESS-domain training (the nightly sync accumulates data), ablate the catalog inputs, calibrate, report the TESS result with CIs, increase `LIGHTCURVE_SYNC_BATCH`/`CENTROID_SYNC_BATCH` or prioritise candidates by follow-up value rather than TOI number order.
9. Adoption (the only thing the repo's own reviews call decisive): ship a one-page triage CSV/VOTable with the flags a TFOP reviewer already uses (RUWE, derived-radius sanity, density discrepancy, odd/even, secondary) each with a cited threshold and provenance, and put it in front of one TFOP subgroup member for a season of feedback, with the above bugs fixed first.
10. Minor: divide proper-motion RA shift by cos(dec); cross-match by Gaia ID (TIC stores it) instead of 5" nearest neighbour; widen CI to include `pl_tranmiderr`; require CI tests to exercise the ML serving path.

### Inferences
- The one claim that should not be made to an observer at present is that the numeric score carries independent cross-catalog evidence; the defensible claim is a convenience prior plus an audit trail of the underlying catalog numbers.
- The most credible narrative the data support: "EEFN reproduces TFOP dispositions at AUC about 0.85-0.92 from TOI table values; adding Gaia/2MASS/PS barely helps; physics flags and provenance are the real contribution; light-curve/centroid evidence is early and unvalidated."

### Gaps
- No evidence on how a real TFOP observer would use or trust it (no user study, no feedback in repo).
- Could not verify the frontend runtime behavior or whether any hardcoded numbers on pages other than those grepped (about, ai-analysis, predictions, showcase, graph, data-pipeline, fusion, candidates/[id]) exist elsewhere.
- Could not independently verify external facts (e.g., TIC-8 radius/distance derived from Gaia DR2 parallax; Gaia GSP-Phot as the source of `Rad`/`Dist`); the near-agreement in the CSV is consistent with this but I did not check catalog documentation or run web searches. The repo's `validation/reports/data_leakage_report.md` itself labels `st_*` as "pre-TESS archives", which conflicts with Gaia-derivation; treat the TIC provenance claim as inference.
