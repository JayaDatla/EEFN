# Centroid / difference-image vetting for TESS, and what TFOP adoption of a vetting aid would require

Provenance note: Twicken+2018 and Guerrero+2021 text was read directly (PDF text extracted locally). Bryson+2013, LEO-Vetter, TFOP pages and tool descriptions were read via a summarising fetch tool or search snippets, so their numbers are second-hand unless marked "direct". "Inference" sections are mine, not documented fact.

## 1. Is the EEFN centroid method (shift / depth, 3 sigma + 2 arcsec floor, empirical null) sound versus SPOC DV and the literature?

### Takeaway
shift/depth is a recognised quantity (it is DV's own Eq. 13, from Wu+2010 and Bryson+2013), so the core idea is sound. But SPOC and Kepler treat flux-weighted centroids as the weaker of two tests, and the 2 arcsec floor is far below the systematic floors those pipelines use for TESS (7.5 arcsec at 3 sigma in DV; 15 arcsec fail threshold in LEO-Vetter). The floor is not harmful but is probably non-binding and unjustified; the empirical-null significance is the right instinct.

### Cited Findings
- DV defines the source offset from the peak centroid shift and fractional depth D as Delta = -delta*(1-D)/D, and inverts it as delta = -Delta*D/(1-D); the sign is opposite the transit source because the centroid moves away from a dimming source. For D << 1 this is shift/depth. Cites Wu+2010 and Bryson+2013. Direct text. — [Twicken+2018, arXiv:1803.04526, Sec. 3.6, Eq. 13-14](https://arxiv.org/pdf/1803.04526)
- Bryson+2013 gives the same small-depth limit: offset ≈ -(centroid shift)/(observed depth) in RA (with 1/cos dec) and Dec. — [Bryson+2013, arXiv:1303.0052](https://ar5iv.labs.arxiv.org/html/1303.0052)
- DV propagates uncertainty including the depth uncertainty term: sigma_delta^2 = (D/(1-D))^2 sigma_Delta^2 + (Delta/(1-D)^2)^2 sigma_D^2. So depth error is part of the formal error budget; shift/depth is not a free-standing ratio. — [Twicken+2018, Eq. 15](https://arxiv.org/pdf/1803.04526)
- DV's centroid-motion test fits the whitened centroid time series against the transit model in RA and Dec, and forms a chi-squared (2 dof) detection statistic t = l_a^2 + l_d^2 with p-value. The whitening handles correlated noise. Direct text. — [Twicken+2018, Sec. 3.6, Eq. 9-12](https://arxiv.org/pdf/1803.04526)
- DV states flux-weighted centroids work only when target and transit source are both well within the photometric aperture; difference-image offsets stay reliable when the background source is outside the aperture. Direct text. — [Twicken+2018, Sec. 3.6](https://arxiv.org/pdf/1803.04526)
- Failure example: KOI-140 flux-weighted centroid gave a 19.8 arcsec (146 sigma) offset when the true background EB was ~5.8 arcsec away, because the source fell on or outside the aperture edge, so depth was underestimated and the offset (shift/depth) overestimated. Direct text. — [Twicken+2018, Sec. 3.6](https://arxiv.org/pdf/1803.04526)
- Bryson+2013: flux-weighted centroids are very sensitive to pixel-value variations (shot noise, stellar variability); the PRF-fit difference image is more robust to variability but sensitive to crowding. Example KOI-1860: centroid method gave a spurious ~4 arcsec offset while the PRF fit placed the source ~0.33 arcsec from the target. Centroid shift can be non-zero even when the target is the source. Variability of a partially captured bright star can produce a spurious transit-correlated centroid shift. — [Bryson+2013](https://ar5iv.labs.arxiv.org/html/1303.0052)
- Bryson+2013 uses D > 3 sigma_D significance (2-dof chi-squared: random exceedance of 3 sigma about 1.1%), flags offsets unreliable if PRF position differs from catalog by more than 1 pixel (3.98 arcsec), requires PRF fit correlation of at least 0.7, and bootstraps over quarterly offsets for non-Gaussian uncertainties. — [Bryson+2013](https://ar5iv.labs.arxiv.org/html/1303.0052)
- Kepler DV trusted offsets "on the order of 0.2 arcsec"; it is not accepted that a background source can be established below 0.2 arcsec. A quadrature error of 0.2/3 = 0.0667 arcsec is added so the minimum 3 sigma offset uncertainty is 0.2 arcsec. Kepler had 3.98 arcsec pixels and up to 17 quarters to average. Direct text. — [Twicken+2018, Sec. 3.4](https://arxiv.org/pdf/1803.04526)
- TESS equivalent: pixel is 21 arcsec and most targets get one sector, so the quadrature term is set such that offsets under 7.5 arcsec are not significant at 3 sigma (about 0.35 pixel). Direct text. — [Guerrero+2021, TOI catalog, arXiv:2103.12538](https://arxiv.org/pdf/2103.12538)
- TESS DV offsets are computed two ways: versus the proper-motion-corrected catalog position (robust against crowding; observed more reliable for crowded TESS images) and versus the PRF centroid of the mean out-of-transit image (not crowding-robust, but cancels common PRF-centroid bias in uncrowded fields). Direct text. — [Guerrero+2021](https://arxiv.org/pdf/2103.12538)
- The TOI+ table carries a "centroid offset flag" set TRUE when the offset is greater than 5 sigma. Direct text. — [Guerrero+2021](https://arxiv.org/pdf/2103.12538)
- Kepler Robovetter (DR25): TCE is an FP for centroid offset if at least 3 difference images show a discernible stellar image and a 3 sigma offset larger than 2 arcsec, or a 4 sigma offset larger than 1 arcsec, is measured, and at least two-thirds of quarterly difference images show it. Offset is difference-image PRF centroid minus out-of-transit PRF centroid; offsets measured only against the KIC position (flag CENT_KIC_POS) are not trusted alone. — [Thompson+2018, arXiv:1710.06758](https://arxiv.org/pdf/1710.06758) (via search summary); [Archive flag docs](https://exoplanetarchive.ipac.caltech.edu/docs/koi_comment_flags.html)
- Note the 2 arcsec in Kepler is 0.5 Kepler pixel (3.98 arcsec/pix) and is paired with a 3 sigma (and a stricter 4 sigma / 1 arcsec arm). The same figure in TESS pixels (21 arcsec) would be about 10 arcsec. (arithmetic from the cited pixel scales)
- LEO-Vetter (2025) pixel test: PRF fit of TESS difference image (transit-diffImage, tess_PRF_centroid), fail as off-target when offset > 15 arcsec; fit quality below 0.3 is untrusted; localisation accuracy about 0.2 pixel (≈5.2 arcsec) at high SNR, degrading at low SNR. The paper does not report precision/recall for the centroid test alone; two known NEB false positives (TOI-633.01, TOI-5648.01) survived both flux and pixel vetting; authors say the threshold favours completeness over reliability. — [LEO-Vetter, arXiv:2509.10619](https://arxiv.org/html/2509.10619v1)
- Centroid precision data (SPOC): flux-weighted centroid formal uncertainties of ~1e-4 pix (Tmag 6), 5e-4 pix (Tmag 9), 2.7e-3 pix (Tmag 12); but short-timescale (2-min) pointing scatter is ~5e-3 pix after modelling, which formal errors do not include. Direct text. — [Guerrero+2021](https://arxiv.org/pdf/2103.12538)
- DV's own centroid example: Kepler-62f peak centroid shift 0.294 ± 0.338 mas (statistic 2.57); KOI-140 shift 13.94 ± 0.098 mas (statistic 32,100). Direct text. — [Twicken+2018](https://arxiv.org/pdf/1803.04526)
- Red-noise/empirical nulls: DV whitens the centroid series before correlating with the transit model, and DV includes a statistical bootstrap test for the flux detection; Bryson+2013 bootstraps quarter-to-quarter offsets. I did not find a TESS-vetting paper that specifically advocates fake-transit-epoch nulls for centroids (see Gaps). — [Twicken+2018](https://arxiv.org/pdf/1803.04526); [Bryson+2013](https://ar5iv.labs.arxiv.org/html/1303.0052)
- Newer approach: Transit-APP (Bryson & Kunimoto 2025) avoids centroids, comparing observed difference image to modelled difference images for each candidate star, giving relative probabilities; described as robust at low SNR where centroids lose precision or fail by sector. Only abstract seen. — [NTRS 20250003461](https://ntrs.nasa.gov/citations/20250003461)
- Most common DV failure on TESS: a nearby bright variable star dominating difference images (larger pixels). — [Guerrero+2021 / search summary](https://arxiv.org/pdf/2103.12538)

### Inferences
- Order-of-magnitude arithmetic for EEFN: with 21 arcsec pixels, a 1000 ppm transit from a source 21 arcsec (1 px) away shifts the photocentre ~21 mas; a source 2 arcsec away at 500 ppm shifts it ~1 mas. SPOC's 2-min scatter (~5e-3 pix ≈ 105 mas) averaged over, say, ~60 in-transit cadences gives ~14 mas per transit before systematics. So the implied-offset 1-sigma for a 1000 ppm event is of order 10+ arcsec, and the 3 sigma cut will bind long before the 2 arcsec floor does. The floor therefore adds little, and a "2 arcsec" figure invites misreading as achieved precision (SPOC refuses to call anything under 7.5 arcsec significant). Suggest reporting the empirical 3 sigma radius and a minimum-detectable-offset per target instead.
- Because 2 arcsec was not tuned on labelled data, it should be labelled as a convention borrowed in spirit from Kepler (3 sigma and 2 arcsec) rather than a calibrated TESS number; the Kepler value presumes 4 arcsec pixels and many quarters.
- Interpreting shift/depth as offset "from the target" is only valid relative to the aperture's out-of-transit photocentre (DV does the same, then re-references to catalog). In crowded apertures the out-of-transit photocentre is not the target, and DV shows this gives significant offsets for genuine planets. EEFN should state the reference point and, ideally, also compute offset versus the Gaia/TIC proper-motion-corrected position as DV does.
- Depth used in the denominator must be the in-aperture (diluted) depth; if the true source is outside the aperture the depth is underestimated and the offset inflated (KOI-140 pattern). Also, shift/depth is only the D<<1 limit, so for deep events use the (1-D)/D form.
- The TOI-104.01 5.4 -> 1.97 sigma retraction is consistent with the literature: white-noise errors on centroids are known to be too optimistic (formal errors exclude pointing scatter), and the move to local baselines plus an empirical null is directionally what DV (whitening) and Bryson (bootstrap) do. A fake-epoch null is a defensible, simple analogue, but must be shown to be calibrated (null z-scores ~ N(0,1) on known on-target planets), and should exclude epochs near momentum dumps and other transits.

### Gaps
- Exact TESS DV/TOI vetting rule for the centroid flag: Guerrero+2021 gives only the 5 sigma flag in TOI+ and the 7.5 arcsec 3 sigma floor; I found no document stating a pass/fail offset in arcsec used by TOI vetters (one secondary source mentions 1 pixel as conservative; not verified).
- Quantitative precision of TESS DV difference-image centroids as a function of Tmag and depth: not located in a primary source. Only the LEO-Vetter 0.2 pixel high-SNR figure and SPOC's raw centroid scatter.
- Precise Robovetter threshold table (Thompson+2018) was read via snippet, not the full table.
- Peer-reviewed quantification of bias of aperture photocentre versus PRF difference image specific to TESS (as opposed to Kepler, Bryson+2013): not found.
- Momentum dumps, differential velocity aberration, saturation/bleed-column effects on TESS centroids: only the SPOC statement that row-centroid uncertainties grow for Tmag < 6 due to saturation and bleed was found; DVA and momentum-dump specifics were not researched in detail (LATTE includes a momentum-dump diagnostic).
- Evidence that fake-epoch/bootstrap nulls specifically improve TESS centroid vetting: not found.

## 2. Available data products and whether EEFN can consume SPOC DV results instead of recomputing

### Takeaway
SPOC already publishes DV difference-image centroid offsets for each TCE, and TESS-SPOC FFI DV products exist since Sector 36. EEFN should ingest those as a baseline (and cross-check), not only recompute.

### Cited Findings
- SPOC DV outputs per target: a DV Results XML file, a DV Time Series FITS file (dvt: sector-stitched, detrended, whitened light curves for all TCEs on the star), a full DV Report PDF and a mini report PDF; reports contain folded light curves and in- and out-of-transit difference images. I could not confirm that the dvt.fits holds centroid or difference-image arrays. — [MAST TESS archive manual](https://outerspace.stsci.edu/display/TESS/2.0+-+Data+Product+Overview)
- Since Sector 36, TESS-SPOC FFI DV products are provided for TCEs, similar to 2-minute DV products; the FFI transit search uses a minimum pulse duration of 2 hours versus 0.5 hours for 2-minute data. — [TESS-SPOC HLSP](https://archive.stsci.edu/hlsp/tess-spoc)
- DV report content for each TCE includes total centroid motion statistic, p-value, peak shift in RA/Dec, source offset and uncertainties (Kepler description; TESS DV report shows the offset plot with 3 sigma radius). — [Twicken+2018](https://arxiv.org/pdf/1803.04526); [Guerrero+2021 Fig. caption](https://arxiv.org/pdf/2103.12538)
- TESS PRF models: official files on MAST (grid every 512 pixels, 81 sub-pixel models per file, sector sets 1-3 and 4+); community wrapper TESS_PRF (Keaton Bell, ASCL 2207.008) interpolates them; I found no official TESS PRF class in lightkurve (lightkurve's PRF tooling is for Kepler). — [TESS_PRF](https://github.com/keatonb/TESS_PRF); [HEASARC TESS tools](https://heasarc.gsfc.nasa.gov/docs/tess/data-analysis-tools.html)
- Existing open PRF-based difference-image code used by LEO-Vetter: transit-diffImage and tess_PRF_centroid (Bryson). — [LEO-Vetter](https://arxiv.org/html/2509.10619v1)
- tpfplotter (Aller+2020) overlays SPOC aperture and Gaia sources on TPFs; ASCL 2504.018; hosted at NASA EMAC. — [EMAC tpfplotter](https://tools.emac.gsfc.nasa.gov/tpfplotter/)

### Inferences
- A tool that adds value beyond SPOC should frame itself as an independent cross-check against DV offsets (show both, report disagreements), because TFOP observers already get DV difference-image offsets via ExoFOP/DV reports.
- Mapping EEFN's photocentre shift to DV's "magnitude of peak centroid shift" and "source offset" is natural since the quantities are identical in definition; this would make direct validation against DV possible.

### Gaps
- Whether DV centroid-offset numbers are accessible machine-readably (XML fields via MAST) and exactly which keywords: not confirmed.
- TESS-Point API details: no source found.

## 3. How TFOP uses tools, and what makes a new tool trusted

### Takeaway
TFOP is a prioritisation-and-coordination machine centred on ExoFOP-TESS, with SG1 doing NEB checks via AstroImageJ and a Transit Finder. I found no evidence of a systematic route by which community vetting tools "graduate" into TFOP, and no adoption statistics; recommendations here are largely inference.

### Cited Findings
- Subgroups: SG1 seeing-limited photometry (find nearby EBs, refine timing; chair K. Collins), SG2 reconnaissance spectroscopy (S. Quinn), SG3 high-resolution imaging (D. Ciardi), SG4 precise RV (D. Latham), SG5 space-based photometry (D. Dragomir); ExoFOP-TESS is a cross-cutting function. — [TESS TFOP page](https://tess.mit.edu/followup); [HEASARC TFOP](https://heasarc.gsfc.nasa.gov/docs/tess/tfop.html)
- Primary mission aim: measure masses of 50 transiting planets under 4 Earth radii; TFOP also exists to avoid duplicate observations. — [TESS TFOP page](https://tess.mit.edu/followup)
- ExoFOP shows subgroup priorities per TOI: larger candidates, or small candidates around stars likely too faint for RV, get SG1/SG2 priority 3; SG3/SG4/SG5 start at priority 4 (on hold) and are updated after SG1/SG2 results. — [HEASARC TFOP summary](https://heasarc.gsfc.nasa.gov/docs/tess/tfop.html)
- SG1 workflow: about 200 members; NEB search of stars within ~2.5 arcmin using ~1.5 arcsec apertures; dispositions VPC / VPC- / NEB (PNEB on first detection); typical ground sensitivity ~1000 ppm; tools AstroImageJ, SG1 TESS Transit Finder, EXOFASTv2; results uploaded to ExoFOP-TESS. NEBs further than ~20 arcsec can be found via FFIs. — [Collins, TSC 2019 talk](https://tsc.mit.edu/2019/talks/Karen%20Collins.pdf); [GMU JSSR](https://journals.gmu.edu/index.php/jssr/article/view/3238)
- TOI triage context: TESS-ExoClass (TEC, public decision tree over SPOC DV metrics) and AstroNet-Triage largely automated triage by Sector 6; humans vet with the TESS Exoplanet Vetter (TEV), 3 to 5 vetters per target. — [Guerrero+2021](https://arxiv.org/pdf/2103.12538)
- LATTE: JOSS paper (Eisner, Lintott, Aigrain 2020, DOI 10.21105/joss.02101), open source Python, LGPL-3.0, pip-installable (tessLATTE), ASCL listing, runs on SPOC 2-min or FFI data, shows momentum dumps, background flux, x/y centroids, etc.; used in the Planet Hunters TESS discovery of TOI-813 b. Note: published 2020, not 2021. — [PyPI](https://pypi.org/project/tessLATTE/0.1.15); [ASCL 2205.006](https://ascl.net/2205.006); [JOSS](https://joss.theoj.org/papers/10.21105/joss.02101)
- tpfplotter (Aller+2020, A&A 635, A128): single-purpose contamination plot from Gaia over TPFs; widely seen in published planet papers' figures (search snippets of TOI-2257, WASP-18 figures). — [EMAC](https://tools.emac.gsfc.nasa.gov/tpfplotter/); [A&A figure pages](https://www.aanda.org/articles/aa/full_html/2021/10/aa41714-21/F6.html)
- ExoFOP data access: the TOI table is available as CSV via download_toi.php?output=csv (also pipe-delimited and per-TOI via toi=); the access is undocumented PHP, wrapped by the community package etta; I saw no JSON option. The NASA Exoplanet Archive hosts a weekly-updated TOI table with documented columns, accessible via its TAP/API. — [etta docs](https://etta.readthedocs.io/en/dev/); [stellarphot source](https://stellarphot.readthedocs.io/stable/_modules/stellarphot/io/tess.html); [Archive TOI columns](https://exoplanetarchive.ipac.caltech.edu/docs/API_toi_columns.html)
- ExoFOP reached one million community-uploaded files (2025 NASA Exoplanet Archive/ExoFOP paper). — [arXiv:2506.03299](https://arxiv.org/abs/2506.03299)

### Inferences
- Reasons small tools like LATTE and tpfplotter stuck (inference, not documented): they do one visual task observers were already doing by hand, output a publication-ready figure, install in one command, are citable (JOSS/A&A + ASCL), and feed the existing workflow (ExoFOP/TIC IDs) without asking observers to trust a new classification. A scored "off-target" flag is a bigger ask than a diagnostic plot.
- The relevant workflow for SG1: NEB flags and which nearby stars could cause the signal. A centroid aid is most useful if it names candidate sources (ranked by Gaia position consistent with the implied offset) and flags which apertures to observe, rather than just reporting an offset in arcsec. At ~10+ arcsec precision (see Section 1) it cannot localise a source to one star; say so.
- Trust requires: TIC/TOI-ID inputs, ExoFOP-compatible CSV (and ideally TAP/VOTable) output, versioned releases with a pinned lightkurve/astroquery environment, published per-target uncertainties and detection limits, and a plain statement that it supplements SPOC DV.

### Gaps
- No quantitative adoption data (downloads, citations) retrieved for LATTE/tpfplotter; no source on how TFOP SG1-4 formally decide to endorse a tool.
- ExoFOP programmatic API completeness (no official docs located).
- Whether TFOP observers use TAP/VOTable for ExoFOP data: not found.
- Not searched in depth: ExoClock, Exo-MAST, TESS Triage product-specific details.

## 4. Minimal credible validation study

### Takeaway
No standard exists; the closest precedents are TRICERATOPS (68 known TOIs) and LEO-Vetter (135 non-FP TOIs; no centroid-only metrics). A credible EEFN study needs labelled on-target vs off-target TOIs, per-target comparison to DV offsets, and reported false-negative rates.

### Cited Findings
- TRICERATOPS benchmark: 68 TOIs known as confirmed planets or astrophysical FPs; thresholds FPP < 0.015 & NFPP < 1e-3 (validated), FPP < 0.5 (likely planet), NFPP > 0.1 (likely nearby FP); applied to 384 TOIs (12 validated, 125 likely planets, 52 likely nearby FPs). A confusion matrix was not seen in snippets. — [Giacalone+2021, AJ 161, 24](https://dspace.mit.edu/bitstream/1721.1/134566/2/Giacalone_2021_AJ_161_24.pdf)
- A 2025 study of 443 candidates found 72% of 68 validated planets with contrast curves would fail validation without them (sensitivity of FPP to inputs). — via TRICERATOPS search summary ([arXiv:2508.02782](https://arxiv.org/abs/2508.02782), not read directly)
- LEO-Vetter: 325 TCEs passing flux vetting, 153 failed pixel vetting; 135 non-FP TOIs checked; no centroid-only precision/recall. — [LEO-Vetter](https://arxiv.org/html/2509.10619v1)
- Kepler precedent for ground-truthed centroid performance: validation against KOIs with known background sources (e.g. KOI-140 offset 19.8 vs 5.8 arcsec true; KOI-1860). — [Twicken+2018](https://arxiv.org/pdf/1803.04526); [Bryson+2013](https://ar5iv.labs.arxiv.org/html/1303.0052)

### Inferences (proposed design; no source defines it)
- Labels: ExoFOP TFOPWG dispositions (CP/KP vs FP with NEB/nearby-star evidence, SG3 resolved companions) with the label source recorded; separate on-target controls (confirmed planets, n of order 100+) from off-target positives (NEBs/background EBs with known separation, n limited, probably tens). State per-class n and Wilson/binomial intervals.
- Pre-specify (before looking at results) the statistic, the threshold(s) and the TOI split; hold out a test set not used for any floor/threshold choice, since the 2 arcsec floor is currently untuned.
- Metrics: false-alarm rate on confirmed planets at the chosen threshold; recall on known off-target FPs as a function of separation (in pixels) and depth/Tmag; calibration of null z-scores; agreement (and disagreement cases) with DV offsets and with LEO-Vetter / TRICERATOPS NFPP; report non-detections explicitly as "uninformative" rather than "on-target".
- Include the retracted TOI-104.01 case as a documented regression test; archive code, data and TIC list with a DOI.

### Gaps
- No pre-registration conventions for TESS vetting tools found.
- No published false-negative rate for any TESS centroid vetting test found.
