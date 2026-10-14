# Automated vetting / false-positive identification for transiting-planet candidates, and where a cross-catalog evidence-consistency audit fits

Research date: 2026-10-13. Method note: ~17 web searches/fetches. Several details came only from search-result summaries or from the first ~100k characters of long arXiv pages; those are flagged. Items I could not source are in Gaps, not Cited Findings.

## 1. What do the main tools actually do and use (SPOC DV, TEC/Robovetter-style, TRICERATOPS, vespa, DAVE, LEO-vetter, ExoMiner/++, AstroNet, TFOP Gaia checks)? Which use Gaia/stellar catalogs, and how?

### Takeaway
Every major tool is anchored on the transit signal itself (flux, centroid/pixel, odd-even, secondary, shape); stellar catalog information enters mostly as (a) a prior/contaminant list (TRICERATOPS, vespa), (b) a scale factor (stellar radius to planet radius, e.g. LEO-vetter size cut), or (c) a few scalar inputs (ExoMiner++ lists RUWE and Tmag). I found no tool whose core signal is "catalog A disagrees with catalog B about the host star".

### Cited Findings
- SPOC Data Validation reports (Twicken+2018; Li+2019) are reviewed by the MIT TOI team, and TOI release decisions turn on DV test thresholds (example: TOI-2096 candidate marginally failed the model-fit/bootstrap test thresholds). — [TOI-2096 paper, arXiv:2303.08174](https://arxiv.org/pdf/2303.08174) (via search summary)
- TESS-ExoClass (TEC) is an automated method for the TSO vetting team to identify planet candidates among SPOC postage-stamp TCEs; it draws on the Kepler Robovetter approach, its tests/thresholds were tuned during the first four sectors to match manual TSO classifications; code is open-source and per-sector classification tables are published. — [TOI-715 paper, arXiv:2305.06206](https://arxiv.org/pdf/2305.06206) (via search summary; I did not obtain TEC's actual rule list)
- Guerrero+2021 describes the TESS Science Office systematic vetting that produces the official TOI list: 2,241 candidates from the prime mission (sectors 1-26); also gives TFOP priority rules (SNR<11 gets priority 2; Rp>4 R_earth or small planets around stars too faint for RV get priority 3 for SG1/SG2; other subgroups start at priority 4 until SG1/SG2 results arrive). — [Guerrero+2021, arXiv:2103.12538](https://arxiv.org/pdf/2103.12538) (via search summaries)
- TRICERATOPS (Giacalone+2021, AJ 161, 24): Bayesian tool; the only TESS tool (per its abstract) that also models transits from nearby contaminating stars, not just the target. Tested on 68 previously dispositioned TOIs to set FPP/NFPP criteria: validated planet = FPP<0.015 and NFPP<1e-3; likely planet = FPP<0.5 and NFPP<1e-3; likely nearby FP = NFPP>0.1. On 384 unclassified TOIs: 12 validated, 125 likely planets, 52 likely nearby FPs. — [Giacalone+2021 (MIT DSpace)](https://dspace.mit.edu/bitstream/1721.1/134566/2/Giacalone_2021_AJ_161_24.pdf); [Princeton record](https://collaborate.princeton.edu/en/publications/vetting-of-384-tess-objects-of-interest-with-triceratops-and-stat/). I could not extract the PDF text, so exactly which Gaia/TIC columns it queries is not confirmed here (GitHub README does not say: [triceratops repo](https://github.com/stevengiacalone/triceratops)).
- TRICERATOPS FPP can be misleading when companions are closer than the sub-pixel/Gaia scale: for TOI 864.01, Gaia DR3 RUWE=1.18 and TRICERATOPS FPP=0.25, NFPP<1e-4, yet TFOP SG1/SG3-type high-resolution imaging reveals a 0.04" companion and the signal is best read as a hierarchical EB. Note v1 of that preprint argued the opposite; later versions replaced it. — [Escolà Rodrigo, arXiv:2601.02171v4](https://arxiv.org/html/2601.02171v4) (single-author preprint; not clearly peer-reviewed)
- vespa (Morton 2012/2016): FPPs for 7,056 KOIs; 1,935 with FPP<1% (1,284 newly validated), 428 likely FPs. — [Morton+2016, arXiv:1605.02825](https://ar5iv.arxiv.org/html/1605.02825)
- Armstrong+2021 (MNRAS 504): Gaussian-process classifier for probabilistic validation using Kepler data and updated Gaia-era stellar information; mean log-loss 0.54 separating confirmed planets from FPs; 50 planets validated; reports discrepancies with vespa and advises against relying on any single validation method. — [Armstrong+2021, arXiv:2008.10516](https://ar5iv.arxiv.org/html/2008.10516)
- DAVE (Kostov+2019, K2 benchmark): open-source automated vetting at pixel level (centroid offsets for nearby-star contamination) and light-curve level (odd/even depth etc.); applied to TESS in the Triple-9 catalogs (999 TOIs per release, >70% pass diagnostics; 144 flagged FP, 146 potential FP in the first). — [Kostov+2019, arXiv:1901.07459](https://arxiv.org/abs/1901.07459); [Triple-9 I, arXiv:2203.15826](https://ar5iv.labs.arxiv.org/html/2203.15826); [Triple-9 II, arXiv:2303.00624](https://arxiv.org/pdf/2303.00624). Search results did not show DAVE itself using Gaia; treat as unconfirmed.
- LEO-vetter (Kunimoto+2025): fully automated flux+pixel vetting modeled on the Kepler Robovetter. Stellar catalog use is limited: planet radius = R_star x Rp/R_star with a 22 R_earth failure cut; centroid offset test uses catalog RA/Dec (fail >15"); no RUWE or Gaia-astrometry test found in the part of the paper I read (first ~100k of ~152k chars). Reported: 91.0% completeness on injections; 99.91% rejection of simulated false alarms; observed catalog reliability 96.97%; flux-level recovery of 125/135 TOIs; 172 candidates after centroid vetting (127 TOIs). Two known-FP TOIs (both NEBs) survived all vetting. — [Kunimoto+2025, arXiv:2509.10619](https://arxiv.org/html/2509.10619v1)
- ExoMiner (Valizadegan+2022, ApJ): at fixed 99% precision recalls 93.6% of Kepler test-set planets vs 76.3% for the best prior classifier; validated 301 Kepler planets. — [Valizadegan+2022, arXiv:2111.10009](https://arxiv.org/abs/2111.10009v2) (figures via search summary; I did not confirm its stellar-parameter inputs from the text).
- ExoMiner++ (Valizadegan+2025, TESS 2-min): adds periodogram, flux trend, difference image, unfolded flux and spacecraft attitude data; 147,568 unlabeled TCEs scored, 7,330 called candidates; 1,797 of 2,506 ExoFOP PC-labelled TOIs scored as candidates. Scalar inputs include Tmag and RUWE (centroid branch) plus DV diagnostics (MES, SES...). — [arXiv:2502.09790](https://arxiv.org/abs/2502.09790); [HTML v3](https://arxiv.org/html/2502.09790v3). ExoMiner++ 2.0 (FFI) adds an image encoding of neighbouring TIC stars' relative position/brightness; PR AUC ~0.95 under multi-source training. — [arXiv:2601.14877](https://arxiv.org/pdf/2601.14877)
- AstroNet-Triage/Vetting (Yu+2019, first network trained on real TESS data): triage reportedly removes ~93% of non-planetary signals without losing completeness (secondary summary; precision of vetting model lower). — [Yu+2019, arXiv:1904.02726](https://ar5iv.arxiv.org/html/1904.02726)
- Exonet-style CNN (Osborn+2020, A&A 633, A53): adds centroid + stellar-parameter inputs; on simulated TESS data 97% average precision and 92% planet accuracy; on real TESS, only 61% of TOI-coincident TCEs recovered as planets; authors caution sim-to-real transfer is worse. — [Osborn+2020, arXiv:1902.08544](https://arxiv.org/pdf/1902.08544)
- Gaia in TFOP-style vetting is used mostly as: neighbour census within the aperture (modeled as blend sources), RUWE and astrometric flags as binarity hints, and as a complement to SG1 (seeing-limited photometry to find NEBs within ~2.5') and SG3 (high-resolution imaging). Examples: THYME VII combined RUWE limits and Gaia source catalog with NIRC2 imaging; THYME X used Gaia sources + SOAR speckle (rules out companions to ~0.2"). — [THYME VII, arXiv:2206.06254](https://arxiv.org/pdf/2206.06254); [THYME X, arXiv:2406.05234](https://arxiv.org/pdf/2406.05234); [TFOP overview, HEASARC](https://heasarc.gsfc.nasa.gov/docs/tess/tfop.html)
- "paired" (Chance+2022) uses Gaia EDR3 RV errors to give the probability of an unresolved companion for Kepler/TESS stars, explicitly pitched for flagging FP-prone candidates. — [arXiv:2206.11275](https://arxiv.org/pdf/2206.11275)

### Inferences
- Gaia binarity indicators (RUWE) are already consumed by at least one deep-learning vetter (ExoMiner++) and implicitly by TFOP planning, so "RUWE flag" alone is not novel.
- TIC-vs-Gaia parameter differences as an explicit score are not described in any tool above; they appear to be implicit (via stellar-radius-derived planet radius cuts and via dilution/contamination modelling).

### Gaps
- TRICERATOPS exact Gaia/TIC column usage (PDF unreadable via fetch); TEC's concrete rule list; DAVE's use of Gaia; ExoMiner's full stellar-parameter inputs; Twicken+2018 DV test list. Primary papers should be read directly.

## 2. Is there published work on cross-catalog consistency / stellar-parameter disagreement as a FP or false-confidence indicator? What fraction of TOI FPs stem from wrong stellar radius/binarity/blends vs instrumental/astrophysical?

### Takeaway
I found only indirect evidence: revised stellar radii flip candidate status (planet radius becomes non-planetary), and unresolved companions bias radii or produce FPs. I found no paper that builds a TIC-vs-Gaia disagreement score and trains it against TFOP dispositions, and no authoritative breakdown of TOI FP causes. So the specific signal looks under-explored (novel as a packaged score), but its constituent ideas are established.

### Cited Findings
- GALAH-based reanalysis: re-derived stellar radii made two candidates nonphysical (~24 and ~35 R_earth), TOI 1072.01 (~28 R_earth) likely a brown dwarf, and TOI 565.01 (previously FP, then APC) now ~25 R_earth, likely an EB; authors argue for vetting before public release. — [Hinkel/GALAH, arXiv:2111.14883](https://arxiv.org/pdf/2111.14883) (via search summary; author attribution not verified)
- SED-based stellar parameters for 99 of 115 TOIs (AstroARIADNE, Gaia DR2 parallaxes) were similar to TIC v8.1 but more precise; median fractional radius error fell from 4.3% to 1.2%. — [BAAS abstract](https://baas.aas.org/pub/2022n6i320p04)
- A 2026 poster comparing confirmed planets vs FPs found candidate radius among the largest-separating diagnostics (KS D = 0.404). — [Nakamori poster](https://vmnexsci.ipac.caltech.edu/workshop/2026/posters/Poster_MoyuruNakamori_31.pdf) (poster, not peer reviewed; caution: radius as a "feature" is strongly confounded with FP physics, i.e. giant radius implies EB)
- FP fractions are heavily radius- and period-dependent: ~49% of hosts with candidates >15 R_earth already FPs; 45%+-5% of TOIs with R>15 R_earth listed FP on ExoFOP (2019 analysis) vs 16%+-3% for 9-15 R_earth; high FP rates at short period/large radius, majority attributed to close eclipsing binaries; southern first-year TOIs 230/1092 = 21.0% FP, later ones 21/367 = 5.7% (pre-ground-vetting). — [SOAR/related TOI statistics via search: arXiv:2103.12076](https://arxiv.org/pdf/2103.12076) and others; I could not pin each number to a specific paper from search summaries, so verify before citing.
- Unresolved/dilutive companions bias planet radii and create FPs; TFOP SG3 and SG1 address them. — [TOI 864.01, arXiv:2601.02171](https://arxiv.org/html/2601.02171v4); [TFOP, HEASARC](https://heasarc.gsfc.nasa.gov/docs/tess/tfop.html)
- Kepler precedent: Gaia-era stellar properties (Berger+2020, 186,301 stars, Gaia DR2) were used to recompute Kepler planet radii; this is stellar-property refinement, not an FP classifier. — [Berger+2020, arXiv:2005.14671](https://arxiv.org/abs/2005.14671)

### Inferences
- "Wrong stellar radius" mostly matters for (a) giant-planet vs EB/BD discrimination and (b) science-grade radius, not for the dominant FP mechanism (blended/eclipsing-binary), which is detected by centroid/odd-even/NEB checks. A catalog-consistency score would therefore mostly proxy for binarity and dilution that RUWE, TIC contamination ratio and imaging already target.
- Stellar-density consistency (transit-derived density vs catalog density) is a classical check but I found no source in this pass documenting its use as an automated TESS FP score; do not claim absence beyond "not found".

### Gaps
- No quantified breakdown of TOI FPs by cause (wrong R*, binarity/blend, instrumental). No paper found training on TIC-Gaia disagreement features. No source found for stellar-density-consistency vetting of TOIs in this pass.

## 3. Reported accuracy/recall/precision on TESS and the evaluation pitfalls authors acknowledge

### Takeaway
Headline numbers are high but depend on label sets and base rates; TESS labels are noisier than Kepler's, and models do worse on TESS than Kepler. A tabular accuracy ~0.85 / AUC ~0.93 for catalog-only features is in the range of published tabular TOI classifiers, but those are not comparable to signal-level vetters.

### Cited Findings
- ExoMiner++ (TESS 2-min, 57,162 labelled TCEs, 3,681 planets = 6.44%): TESS+Kepler aggregate precision 0.933, recall 0.951, PR AUC 0.976, ROC AUC 0.998 (at 0.5 threshold); TESS-only individual 0.918/0.917; Kepler baseline 0.976/0.965. Labels from ExoFOP KP/CP/FP, Villanova EB catalog, TEC; PC and APC excluded. Authors' caveats: ExoFOP dispositions vary in certainty, EB labels are manual and imperfect, ephemeris matching misses weak secondaries, brown dwarfs hard to separate, FPs are the hardest class, performance lower on TESS than Kepler. — [arXiv:2502.09790v3](https://arxiv.org/html/2502.09790v3)
- LEO-vetter limitations: assumes strictly periodic circular orbits, no TTVs, grazing transits poorly fit, reduced performance at 30-min cadence and weak signals, thresholds depend on optimization choices, users should do their own FP analysis afterwards. — [arXiv:2509.10619](https://arxiv.org/html/2509.10619v1)
- Osborn+2020: sim-to-real gap (61% of TOI-coincident TCEs recovered). — [arXiv:1902.08544](https://arxiv.org/pdf/1902.08544)
- Robovetter DR25: ~85% completeness, ~97% reliability overall, but in low-MES long-period region reliability can be ~45%; reliability varies with period, SNR, stellar type. — [Thompson+2018, arXiv:1710.06758](https://arxiv.org/pdf/1710.06758); [exoPAG slides](https://exoplanets.nasa.gov/system/presentations/files/151_20200104-0830_Mullally_Exopag21.pdf)
- ExoMiner independent-test recall: WATSON-Net reports ExoMiner recalls of 0.92/0.88/0.57 at its own thresholds (not comparable to 99%-precision figure). — [WATSON-Net, arXiv:2511.08768](https://arxiv.org/pdf/2511.08768)
- Tabular examples: Random Forest AUC 0.941 vs gradient boosting 0.926 on TOI table (CMU capstone poster; not peer reviewed); XGBoost on KOI (period, duration, depth, SNR) accuracy 0.73, ROC-AUC 0.855 (student/Hugging Face project; low reliability). — [CMU poster](https://www.stat.cmu.edu/capstoneresearch/fall2021/290files/poster4.pdf); [ExoMAC-KKT](https://huggingface.co/ZapatoProgramming/ExoMAC-KKT)
- Triple-9 / NotPlaNET note subjective labels as a limitation. — [NotPlaNET, arXiv:2405.18278](https://arxiv.org/pdf/2405.18278)

### Inferences
- Pitfalls that apply directly to EEFN's design (my reasoning, not from the sources): TFOP dispositions are partly derived from the same catalog/Gaia checks (label leakage into any Gaia-based feature); PC/APC exclusion and survivorship (FPs get dispositioned because they were easy to identify); multiple TOIs per star require star-grouped splits; tabular features like planet radius or depth are confounded with FP class. A cross-catalog score should be reported with and without radius/period-type features.

### Gaps
- No peer-reviewed number for a catalog-only classifier on TESS dispositions with grouped CV.

## 4. How observers triage TOIs for follow-up; what formats/APIs they expect

### Takeaway
Triage runs through the TOI release (SPOC DV + TSO review, TEC), TFOP subgroups (SG1 photometry, SG2 recon spectroscopy, SG3 high-res imaging, SG4 RV, SG5 space photometry) with ExoFOP priority/disposition fields. Observers consume ExoFOP-TESS and the NASA Exoplanet Archive TOI table.

### Cited Findings
- TFOP: five subgroups SG1-SG5; SG1 hunts nearby eclipsing binaries (search within 2.5'; PNEB then NEB dispositions); subgroup leads synthesize final dispositions and not all posted observations feed into them. — [HEASARC TFOP](https://heasarc.gsfc.nasa.gov/docs/tess/tfop.html); [Collins TSC talk](https://tsc.mit.edu/2019/talks/Karen%20Collins.pdf); [JWST TOI selection, arXiv:2308.09617](https://arxiv.org/pdf/2308.09617)
- Priority rules for TOIs are in Guerrero+2021 (see Section 1). — [arXiv:2103.12538](https://arxiv.org/pdf/2103.12538)
- ExoFOP-TESS hosts the TOI table (8,151 TOIs on the day fetched), the CTL download (CTL_v8_ExoFOP-TESS.csv.gz), observation uploads by type (Imaging 36,901; Spectroscopy 34,768; Time Series 22,388; Stellar Companions 9,662), and Python notebooks. — [ExoFOP-TESS](https://exofop.ipac.caltech.edu/tess/)
- NASA Exoplanet Archive TOI table: tfopwg_disp values APC, CP, FA, FP, KP, PC; stellar columns (Tmag, distance, Teff, logg, radius) come from the TIC; TAP interface available. — [TOI column docs](https://exoplanetarchive.ipac.caltech.edu/docs/API_TOI_columns.html)

### Inferences
- Because stellar columns in the TOI table are TIC-sourced, a TIC-vs-Gaia comparison is a natural, cheap add-on, and the Archive TAP/CSV route is the expected input format. Observer-facing outputs would naturally key on TOI/TIC ID and be exportable as CSV/VOTable.

### Gaps
- Official ExoFOP download-function/API parameter docs and help.php were not retrieved; exact priority semantics beyond Guerrero+2021 unconfirmed; no survey of what vetting tools observers "trust" (only anecdotal use of DAVE+TRICERATOPS in validation papers).

## 5. Honest assessment: is a standalone catalog-consistency score worthwhile or subsumed?

### Takeaway
Partly subsumed, partly open. The mechanisms behind catalog disagreement (unresolved binaries, blends, wrong radii) are already addressed by TRICERATOPS/vespa (blend scenarios), DV/LEO-vetter/ExoMiner++ (centroid, RUWE input), and TFOP imaging. What appears absent is a lightweight, transparent, light-curve-free audit of catalog record internal consistency. Its value is as a cheap pre-screen and explanation layer, not as a replacement vetter. Claims of added value need an ablation against simple baselines.

### Cited Findings
- ExoMiner++ already ingests RUWE and Tmag. — [arXiv:2502.09790v3](https://arxiv.org/html/2502.09790v3)
- TRICERATOPS and ExoMiner++ 2.0 explicitly model neighbouring (Gaia/TIC) stars. — [Giacalone+2021](https://dspace.mit.edu/bitstream/1721.1/134566/2/Giacalone_2021_AJ_161_24.pdf); [arXiv:2601.14877](https://arxiv.org/pdf/2601.14877)
- Stellar-parameter refinement demonstrably changes candidate interpretation. — [arXiv:2111.14883](https://arxiv.org/pdf/2111.14883); [BAAS](https://baas.aas.org/pub/2022n6i320p04)
- Even Gaia-clean (RUWE ~1.2) hosts can hide sub-0.1" companions, so catalog consistency cannot replace imaging. — [arXiv:2601.02171v4](https://arxiv.org/html/2601.02171v4)
- Armstrong+2021 advise against single-method validation, supporting complementary independent evidence streams. — [arXiv:2008.10516](https://ar5iv.arxiv.org/html/2008.10516)

### Inferences
- Novelty is modest: the pieces are established; the packaging (TOI-level, TIC vs Gaia DR3 vs 2MASS/Pan-STARRS disagreement metrics trained on TFOP labels) was not found in literature in this pass, but absence of search hits is weak evidence.
- Risk: label leakage and confounding (TFOP dispositions use Gaia-based reasoning; radius/period cues predict FPs on their own). EEFN should test whether disagreement features add AUC beyond radius, period, depth, Tmag and RUWE alone, and beyond TIC contamination ratio, using star-grouped CV.
- Framing suggestion: present as "catalog hygiene / data-quality audit that flags TOIs whose stellar inputs are suspect (and therefore whose derived planet radius and priority are suspect)", complementary to, not competing with, DV/TRICERATOPS/ExoMiner++; avoid claiming it predicts FP better than signal-based vetters. Compare numerically only to tabular baselines, not to ExoMiner++ (PR AUC ~0.97).

### Gaps
- No head-to-head benchmark exists for catalog-only vs signal-based vetting on the same TOI set. I did not search for 2026 literature specifically on TIC v8.2/Gaia DR3 radius revisions beyond what is cited; recommend a follow-up targeted search ("TIC v8.2", "Gaia DR3 TOI stellar radius revision", "stellar density transit consistency TESS vetting").
