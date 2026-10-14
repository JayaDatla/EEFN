# ML validation methodology for exoplanet-candidate vetting (EEFN review)

Research caveat: ~16 tool calls. Several primary papers were only readable at abstract level via the fetch tool (noted below). Items marked "[unverified: background knowledge]" were NOT confirmed against a fetched source. Statistics marked "[my calculation]" are mine.

## 1. Label leakage / circularity (features vs. dispositions); Kepler FP-flag labelling; cleaner label sets

### Takeaway
Leakage is a documented, cross-field failure mode (Kapoor & Narayanan: 329 papers in 17 fields), and the vetting literature mitigates label noise mainly by using stricter label sets (confirmed planets + Certified FPs) rather than by proving absence of circularity. Kepler KOI FP flags and Robovetter labels are themselves outputs of rule-based tests on centroid, secondary-eclipse and shape diagnostics, so a model trained to reproduce them partly learns the Robovetter's thresholds; I found no paper that directly quantifies this circularity.

### Cited Findings
- Kapoor & Narayanan surveyed 17 fields, found leakage affecting 329 papers, proposed a taxonomy of 8 leakage types and "model info sheets"; in civil-war prediction, complex ML advantage over logistic regression vanished after leakage correction. — [arXiv 2207.07048](https://arxiv.org/abs/2207.07048)
- DR25 FPs carry four major flags: Not Transit-Like (NTL), Stellar Eclipse/Secondary (SS), Centroid Offset (CO), Ephemeris Match (EM). The Robovetter (Coughlin+2016, automating human dispositioning) is a rule/decision-tree tool; the older "centroid Robovetter" (Mullally) flagged centroid-offset FPs automatically. — [IPAC Robovetter flags doc](https://exoplanetarchive.ipac.caltech.edu/docs/koi_comment_flags.html); [Thompson+2018, arXiv 1710.06758](https://arxiv.org/abs/1710.06758)
- Minor flags such as CENT_FEW_DIFFS / CENT_FEW_MEAS (fewer than 3 high-SNR difference images) mean the centroid test is often not applicable; all FP KOIs have >=1 minor flag. — [IPAC flags doc](https://exoplanetarchive.ipac.caltech.edu/docs/koi_comment_flags.html)
- DR25 catalog: 8,054 KOIs, 4,034 PCs; for P<100 d completeness >85% and reliability >98%; for low-SNR 200-500 d FGK candidates, 76.7% complete and 50.5% reliable. Completeness/reliability were measured with injected and scrambled/inverted simulated data. — [Thompson+2018 abstract](https://arxiv.org/abs/1710.06758)
- Robovetter errors: of 25,978 signals rejected as non-astrophysical, 306 borderline cases were inspected and 6 (2%) passed human examination as real transits/eclipses. — [Rescuing Unrecognized Candidates, arXiv 2109.05398](https://arxiv.org/pdf/2109.05398) (as summarized by search; not fully read)
- The Autovetter (McCauliff+2015) random forest was trained on (mostly) human dispositions, not Robovetter output, giving a partly independent label source; reported 5.85% overall error, 2.81% for PCs. — [Autovetter doc KSCI-19091-001](https://exoplanetarchive.ipac.caltech.edu/docs/KSCI-19091-001.pdf); [McCauliff+2015, arXiv 1408.1496](https://arxiv.org/pdf/1408.1496)
- ExoMiner Kepler labels: PC = only confirmed planets in the cumulative KOI table (unconfirmed PCs excluded "to reduce label noise"); AFP = Kepler Certified FPs (Bryson+2015); NTP = DR25 TCEs not in cumulative KOI plus Certified False Alarms. Split 80/10/10 plus 10-fold CV. — [ExoMiner, ar5iv 2111.10009](https://ar5iv.arxiv.org/html/2111.10009)
- ExoMiner++ TESS labels come from ExoFOP TOI dispositions (KP/CP vs FP; PC and APC excluded), then the Villanova TESS EB catalog (~4,500 EBs), then TESS-ExoClass flux triage for non-transiting phenomena; authors state labels "are not perfect" (EB catalog classified from light-curve shape alone). — [ExoMiner++, arXiv 2502.09790 HTML](https://arxiv.org/html/2502.09790v1)
- Mitigating circularity in a rule-based vetter: LEO-Vetter's own authors note thresholds were optimized on the same observed/injected/scrambled sets used to report 91.0% completeness and 96.97% reliability, i.e. tuning-set numbers, and TOI/TFOP dispositions are both the benchmark and part of the cleaning. Two TFOP FPs (TOI-633.01, TOI-5648.01) survived flux and pixel vetting. — [LEO-Vetter, arXiv 2509.10619](https://arxiv.org/html/2509.10619v1)
- Armstrong+2021 (GP classifier, validation framing): requires classifier probability >0.99 together with vespa FPP<0.01 and MES>10.5 for validation; it validated 50 planets, reports log-loss 0.54, and cautions vespa disagrees for many others and against reliance on a single method. — [arXiv 2008.10516](https://arxiv.org/abs/2008.10516); thresholds as described in [ExoMiner, ar5iv](https://ar5iv.arxiv.org/html/2111.10009)

### Inferences
- fpflag_co is defined by a centroid test and fpflag_ss by a secondary-eclipse test. Your EB class (fpflag_ss or fpflag_co) therefore mixes (i) a label derived from a diagnostic you DO compute (secondary eclipse: mild circularity, same signal) and (ii) a label derived from a diagnostic you do NOT input (centroid offset). For the CO subset, a model without centroid input can only succeed through correlates (depth, shape, implied radius, stellar properties); high accuracy there would reflect proxy features, not detection of the true mechanism. Recommend reporting per-flag recall (SS-only, CO-only, both) to see which subset drives accuracy.
- "Planet" in the cumulative KOI table includes unconfirmed candidates; ExoMiner's choice of confirmed-only plus Certified FP is the cleaner precedent. Consider restricting to CONFIRMED vs Certified-FP (Bryson+2015) at the cost of n.
- For TESS, the cleanest truth is CP/KP vs FP with documented follow-up reason (RV, imaging, SB1/SB2 reconnaissance). FPs rejected by the same SPOC/QLP DV diagnostics (centroid, odd-even) used as features are circular; FPs established by ground-based follow-up are less so. Record the FP provenance per TOI if available (ExoFOP comments/tags) and report metrics stratified by it. [my recommendation]
- Pure "pre/post Gaia EDR3" ablations are weak proxies; stronger tests would be (a) removing Gaia-derived features and comparing performance (a feature-ablation upper bound on leakage), (b) restricting to FPs/planets resolved by follow-up that does not use Gaia, (c) a time-ordered split. [my inference]

### Gaps
- No paper found that explicitly measures how much a model trained on Robovetter/KOI FP flags re-learns the Robovetter thresholds.
- Thompson+2018 full text (exact Certified-FP / flag definitions) not read; only abstract and IPAC flag page.
- Tey+2023 and Shallue & Vanderburg 2018 label construction not verified beyond abstracts.

## 2. Evaluation protocol, metrics, CI for n=50, "agreement with TFOP"

### Takeaway
Best published practice splits by target star (ExoMiner++ uses 10-fold CV split by target star), reports PR-AUC and recall at fixed precision, and holds out later data (Tey+2023 tested on held-out First Extended Mission data). "Agreement with TFOP labels" is acceptable only as accuracy on a labelled set with CIs and per-class precision/recall; with n=50, 76% has a wide interval.

### Cited Findings
- ExoMiner++: 10-fold CV split by target star; each fold ensembles 10 models; validation/test only TESS. TESS-only aggregate: precision 0.926, recall 0.945, PR AUC 0.967, ROC AUC 0.995; TESS+Kepler aggregate: P 0.933, R 0.951, PR AUC 0.976. Labeled counts: 3,681 exoplanet TCEs vs 53,481 non-planet (857 vs 42,018 at event level). — [arXiv 2502.09790 HTML](https://arxiv.org/html/2502.09790v1)
- ExoMiner headline metric is recall at fixed precision: 93.6% recall at 99% precision on test set vs 76.3% for best existing classifier. — [arXiv 2111.10009](https://arxiv.org/abs/2111.10009)
- Tey+2023 (Astronet-Triage-v2): 99.6% recall at 75.7% precision on test set; held-out 1st Extended Mission data PR-AUC 0.965 (+4% vs Astronet-Triage); recovers 3,577 of 4,140 TOIs vs 3,349 for v1 at equal precision; deployed in QLP triage. — [arXiv 2301.01371 summary via search](https://arxiv.org/abs/2301.01371), [AJ 165, 95](https://research.usq.edu.au/download/f416e5a7cc693bcde6f026857f707204d92a569a73785878a612310ef79ab874/7446360/Tey_2023_AJ_165_95.pdf) (abstract-level only)
- Roberts+2017: random CV is over-optimistic for dependent data; blocked CV (by group, space, time) is almost always more appropriate; recommended whenever dependence exists even if residuals show none. — [Ecography 40:913](https://pred.uni-regensburg.de/id/eprint/1455/)
- A 2026 review (HZ-search with AI) argues transfer gains should be measured on target-domain data kept out of training, hyperparameter selection and fine-tuning, with a no-transfer baseline. — [arXiv 2608.21129](https://arxiv.org/pdf/2608.21129) (secondhand via search summary)
- Label noise: a CNN study found performance degrades roughly linearly up to ~45% label contamination. — [arXiv 1907.11109](https://arxiv.org/pdf/1907.11109) (secondhand)

### Inferences
- Binomial interval for 38/50 = 76%: Wilson 95% CI ~ [0.63, 0.86]; exact Clopper-Pearson roughly [0.62, 0.87] [my calculation]. So 76% is statistically indistinguishable from ~65% or ~85%. Report with CI, and with n of each class (accuracy is misleading if the 50 are class-imbalanced; report balanced accuracy, per-class recall, PR-AUC; AUC 0.81 at n=50 has a CI of roughly +/-0.12 by Hanley-McNeil-type approximations [my estimate, not computed exactly]; use bootstrap by star).
- Kepler CV 82.9% +/- 5.6%: that SD is across folds/repeats, not a CI on generalisation; repeated CV underestimates variance because repeats reuse the same 205 samples (Bengio & Grandvalet 2004 [unverified: background knowledge]). Use nested CV for any hyperparameter choice, and report a bootstrap-by-star CI.
- Comparing CNN (64%) vs LightGBM (82.9%) on the same folds: use paired tests on identical folds (McNemar on pooled out-of-fold predictions or paired bootstrap by star); with n=205 a ~19 pt gap is likely real, but a gap of <5 pts would not be. The CNN comparison also confounds architecture with data size (3.9M parameters vs 205 examples), so "CNN worse" is expected, not a finding about CNNs. [inference]
- "Agreement with TFOP labels" is defensible only as measured accuracy on TFOP-labelled objects; it is NOT validation of Kepler->TESS transfer unless TOIs were excluded from training and the TESS sample is not selected on easy cases (e.g. objects with SPOC 2-min light curves and clear dispositions). Also note TFOP FP labels often derive from the same SPOC DV centroid/odd-even diagnostics, so agreement is partly circular for features of that type.
- Multi-planet systems: group by star (TIC/KIC) at minimum; for TESS also consider grouping by sector/orbit or time (leave-one-sector-out) to detect sector-specific systematics. Standard practice in ExoMiner++ is grouping by target star.
- Prefer metrics at the operating point observers care about: recall at fixed precision (ExoMiner) and PR-AUC; ROC-AUC is insensitive to imbalance.

### Gaps
- No source found giving a canonical test for comparing vetting classifiers on small n; recommendations above are general statistics practice.
- Exact fold/grouping details of Tey+2023 not verified.

## 3. Cross-mission shift Kepler -> TESS

### Takeaway
Published work shows Kepler-trained models need TESS data to work well; the best results come from joint/transfer training on Kepler + TESS with TESS-only evaluation. Directly applying a Kepler-trained light-curve model to TESS (as EEFN does: 76% agreement) is below what in-domain TESS training achieves in the literature, though metrics are not comparable.

### Cited Findings
- ExoMiner++ (TESS 2-min): TESS-only training PR AUC 0.966-0.967; adding Kepler (transfer) raised it to 0.970-0.976; Kepler-only on Kepler is PR AUC ~0.994 (table layout partially garbled in fetch). Confidence is highest on Kepler. Transfer helped across thresholds and raised BD recall 0.531->0.719 (individual models). — [arXiv 2502.09790 HTML](https://arxiv.org/html/2502.09790v1)
- ExoMiner++ added TESS-specific inputs: periodogram, flux trend, difference image, unfolded flux, spacecraft attitude control data; applied to 147,568 unlabeled TCEs, 7,330 flagged PC; 1,797 of 2,506 ExoFOP PC TOIs recovered. — [arXiv 2502.09790](https://arxiv.org/abs/2502.09790)
- ExoMiner++ 2.0 (FFI): PR AUC ~0.95 under multi-source training; adds neighbouring-star location/brightness encoding. — [arXiv 2601.14877](https://arxiv.org/html/2601.14877v2) (secondhand via search summary)
- ExoNet paper identifies shift in period distribution (Kepler median ~11.3 d vs TESS ~4.4 d), stellar population (hotter, more M/K dwarfs), and noise/pixel scale (larger TESS pixels, more contamination); suggests absolute probabilities 50-80% are least trustworthy. — [arXiv 2604.15560](https://arxiv.org/pdf/2604.15560) (secondhand; I did not read the paper)
- Astronet-Triage/Vetting (Yu+2019) were the first CNNs trained and tested on real TESS data; Tey+2023 retrained on a manually reviewed FFI dataset. — [arXiv 1904.02726](https://ar5iv.arxiv.org/html/1904.02726); [Tey+2023](https://arxiv.org/abs/2301.01371)
- LEO-Vetter (rule-based) 93% of non-FP TOIs pass flux-level vetting (125/135); completeness depends on cadence/mission stage (69.88% Prime-only vs ~88-89% extended). — [arXiv 2509.10619](https://arxiv.org/html/2509.10619v1)

### Inferences
- Features that depend on the number of transits, per-point noise and cadence (shape, odd/even depth difference, secondary depth SNR) have different noise floors in TESS (fewer transits, 2-min vs 30-min Kepler long cadence). A Kepler-trained model will mis-calibrate "significance" even if features are scale-free. Mitigations in order of strength: (1) train on TESS TCEs/TOIs directly (grouped CV), (2) pool Kepler + TESS with a mission indicator or Kepler-as-pretraining (ExoMiner++ evidence), (3) inject Kepler-like signals into TESS light curves / degrade Kepler to TESS noise and transit count, (4) use SNR-normalised features and report performance per SNR/period bin.
- A 205-KOI training set is ~1/13 of the Kepler labelled set in ExoMiner (2,654 exoplanets + 28,287 non-planets in Table 4), so there is room to use far more Kepler (and TESS) labels with the same engineered features. [inference]
- Typical accuracy drop from in-domain: not reported in a comparable form; no source gives a standard "Kepler-only on TESS" number. Do not quote one.

### Gaps
- No fetched paper reporting zero-shot Kepler-trained model accuracy on TESS.
- Domain-adaptation (e.g. adversarial) papers for transit vetting not found.

## 4. Missing-data handling

### Takeaway
Missingness that occurs only in one class is an informative-missingness shortcut; the theoretical literature says tree methods that incorporate missingness can exploit it (good if the mechanism is stable, harmful if it differs at deployment). Masking augmentation (your fix) is a defensible approach; the cleanest fix is a stratified audit to confirm missingness is not class-confounded in training and then drop or randomise it.

### Cited Findings
- Josse et al.: for prediction, mean/constant imputation is consistent when missingness is non-informative; for trees, "missing incorporated in attribute" (MIA) handles both informative and non-informative missingness. — [arXiv 1902.06931](https://arxiv.org/pdf/1902.06931) (search summary; theorem conditions not read)

### Inferences
- Your finding (missing radius only in Not-Transit-Like KOIs) is the textbook case where MIA-style tree splits learn P(class | missing). LightGBM's default sends missing values down a learned direction, so this is exactly the reported failure. Options: (a) drop the feature, (b) impute at training and deployment identically with no indicator, (c) randomly mask the feature in all classes during training (what you did), which breaks the association by construction but means the model never uses radius information when present at high rate; verify with a model-wise check that predictions on masked vs unmasked inputs agree, (d) verify missingness mechanisms in TESS (missing radius rate in TESS TOIs is likely small and unrelated to class), so the shortcut may not transfer. [inference; no direct cited evidence]
- Calibration under missingness: calibrate separately or at least report calibration on subsets with/without missing features. [inference]

### Gaps
- No astronomy-specific paper found on missingness shortcuts in KOI/TOI vetting.
- Empirical comparisons of impute vs mask vs drop on small tabular data not retrieved.

## 5. Calibration

### Takeaway
Armstrong+2021 and ExoMiner both treat probabilities as meaningful only if calibrated; ExoMiner does not describe a calibration procedure, so its score is a ranking score, not a probability. Uncalibrated scores shown to observers as "planet probability" would be an overclaim.

### Cited Findings
- ExoMiner's output is a sigmoid score interpreted as likelihood of PC, default threshold 0.5 changeable for precision/recall; no calibration procedure described; related-work text notes a discriminative model can support validation "if the model is calibrated". — [ExoMiner, ar5iv 2111.10009](https://ar5iv.arxiv.org/html/2111.10009)
- Armstrong+2021 reports log-loss (0.54) and uses a probability >0.99 for validation, i.e. treats output as probability. — [arXiv 2008.10516](https://arxiv.org/abs/2008.10516)
- ExoMiner++ catalog gives "confidence scores"; meaning/calibration not defined in the abstract. — [arXiv 2502.09790](https://arxiv.org/abs/2502.09790)
- Guo+2017 (PDF could not be parsed by the fetch tool): [unverified: background knowledge] modern networks are miscalibrated, ECE (binned |accuracy - confidence|) is the standard metric, temperature scaling is a one-parameter fix that works well; isotonic regression is more flexible but overfits with few points; Platt scaling is a 2-parameter alternative. Source: [arXiv 1706.04599](https://arxiv.org/abs/1706.04599).

### Inferences
- With ~205 (Kepler) or ~2,667 (TESS) samples, use Platt/temperature scaling (1-2 parameters) fit on out-of-fold predictions (cross-fitted), not isotonic on 205 points. ECE with 10 bins on n=50 is too noisy; report reliability diagram with Wilson bars, Brier score and log-loss.
- Calibration is dataset-specific: a probability calibrated on Kepler KOIs does not transfer to TESS (different class priors, noise). Show observers either a rank/tier ("high/medium/low", with measured precision per tier) or calibrated-on-TESS probabilities. Base rates matter: a "planet probability" must incorporate the TESS prior, which is not 50:50. [inference]

### Gaps
- Could not verify Guo+2017 contents from the fetched file; no source on isotonic vs Platt sample-size thresholds was retrieved.
- ExoMiner++ full-text calibration section not read.

## 6. Small data: trees vs CNNs; most discriminative features

### Takeaway
Evidence that engineered-feature tree ensembles match or beat deep models on small/imbalanced light-curve data is indirect but consistent, and your 82.9% vs 64% result fits it; the literature's strongest discriminators are centroid/difference-image tests, odd-even and secondary-eclipse depth, shape, and stellar parameters.

### Cited Findings
- Autovetter random forest on engineered TCE attributes: 5.85% overall error, 2.81% PC error; RF described as robust to training-label errors. — [McCauliff+2015](https://arxiv.org/pdf/1408.1496)
- LightGBM on 789 TSFresh features for Kepler: AUC 0.948, comparable to state-of-the-art deep learning at far lower cost. — [arXiv 2011.14135](https://arxiv.org/abs/2011.14135v2)
- Kepler/OGLE variable stars: boosted trees AP 0.81 on Kepler; a Kepler LSTM yielded no successful predictions while feature engineering worked. — [arXiv 1906.06628](https://ar5iv.labs.arxiv.org/html/1906.06628); [arXiv 1710.06804](https://arxiv.org/pdf/1710.06804) (via search summaries)
- Counterpoint: CNN/multi-branch models with large labelled sets (ExoMiner, 2,654 Kepler exoplanets + 28,287 non-planets in ExoMiner++ Table 4) reach recall 0.936 at 99% precision, beyond what small-data feature models report. — [ExoMiner](https://arxiv.org/abs/2111.10009), [ExoMiner++](https://arxiv.org/html/2502.09790v1)
- ExoMiner's input set is the expert-vetting set: full-orbit and transit-view flux, centroid, secondary eclipse, odd/even, stellar parameters, DV scalars; ablation numbers were not in the readable portion. — [ExoMiner, ar5iv](https://ar5iv.arxiv.org/html/2111.10009)
- ExoMiner++ added difference-image, periodogram and attitude-control inputs; ExoMiner++ 2.0 added neighbouring-star encoding for off-target contamination. — [arXiv 2502.09790](https://arxiv.org/abs/2502.09790); [arXiv 2601.14877](https://arxiv.org/html/2601.14877v2)
- LEO-Vetter pixel-level centroid test (offset >15") removed 153 of 325 TCEs that passed flux-level vetting (about 47%), illustrating how much FP rejection comes from pixel-level information. — [arXiv 2509.10619](https://arxiv.org/html/2509.10619v1)

### Inferences
- A light-curve-only vetter (no centroid or difference image) cannot catch the off-target contamination class that centroid tests remove in nearly half of flux-level survivors in LEO-Vetter; document this ceiling and call output "light-curve vetting" not "FP probability".
- Tree models on physics features are the right choice at n~200; if more labels are used (thousands from Kepler DR25 + TESS), revisit a small 1-D CNN with proper regularisation and compare via grouped CV with paired tests.
- The 64% CNN result mostly reflects capacity vs n; do not present it as evidence against CNNs.

### Gaps
- No head-to-head GBM vs CNN on identical small Kepler vetting datasets found.
- No quantitative feature-importance/ablation table from ExoMiner retrieved.

## Prioritised methodological weaknesses in EEFN setup (my synthesis; inferences)
1. Light-curve vetter trained on 205 KOIs while ~30k labelled Kepler TCEs and ~3.7k TESS exoplanet TCEs exist; extend labels and use star-grouped CV with bootstrap CIs.
2. 76% (n=50) has a ~[0.63, 0.86] Wilson CI; report class-wise numbers and do not claim transfer from it.
3. Agreement with TFOP labels is partly circular if TFOP FPs were identified using the same SPOC diagnostics; stratify by FP provenance.
4. EB label contains CO (centroid) component the model cannot see; report per-flag recall.
5. Missingness shortcut fixed by masking; verify and document; apply the same audit to every feature present in one class only.
6. Uncalibrated scores: calibrate on TESS out-of-fold predictions (Platt/temperature) or show tiers with measured precision.
7. Catalog model: Gaia features used by labellers; run a feature-ablation and time-ordered split; treat 0.854/0.927 as an optimistic bound until then.
