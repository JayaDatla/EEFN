# EEFN vs. Published Vetting Tools

**Status**: Methodology-level comparison, not an empirical benchmark.
**Scope**: UPGRADE_PLAN.md E.4 — "Compare against published vetting tools on a common
target set... determine honestly whether EEFN adds signal on top of these... and say
so explicitly rather than implying novelty without checking."

## What this document is, and isn't

This is a comparison of what each tool actually *measures* and *outputs*, based on
their published methodology papers, not a head-to-head run of all tools against a
shared set of TOIs producing directly comparable accuracy/precision/recall numbers.
That empirical benchmark is real, valuable future work — it isn't done here because
it requires infrastructure this environment doesn't have: TRICERATOPS needs TESS
pixel-level data and a stellar-density prior pipeline; AstroNet and ExoMiner need
their published pretrained checkpoints (or a from-scratch retrain, which would take
its own multi-week project) plus the specific light-curve preprocessing each was
trained on. Reporting fabricated numbers for a comparison that wasn't actually run
would violate the same honesty principle this whole upgrade plan exists to enforce
(see UPGRADE_PLAN.md's "Never fabricate" instruction) — so this document instead does
the comparison that *is* honestly available: what evidence each tool uses, and
whether that evidence overlaps with what EEFN uses.

## Summary table

| Tool | Primary evidence source | Output | Maturity |
|---|---|---|---|
| **TRICERATOPS** (Giacalone & Dressing 2020) | Transit light-curve shape + stellar density prior + TESS pixel-level analysis of which nearby star the signal actually originates from | Bayesian False Positive Probability (FPP) and Nearby False Positive Probability (NFPP) per scenario (unresolved EB, nearby EB, etc.) | Actively used by TFOP; FPP values are routinely cited directly in peer-reviewed TOI confirmation papers |
| **Robovetter** (Coughlin et al., Kepler pipeline) | Rule-based diagnostic tests on Kepler TCEs: odd-even depth mismatch, secondary eclipse test, centroid offset test, etc. | Binary disposition (PC/FP) + which specific test(s) failed | Built specifically for Kepler; not actively used for TESS in its original form (TESS uses SPOC/QLP + human TFOP review instead) |
| **AstroNet / AstroNet-Vetting** (Shallue & Vanderburg 2018; Yu et al. 2019 TESS variant) | CNN over folded global+local light-curve views | Binary/multi-class transit classification probability | Established; methodologically the closest thing to EEFN's own DL branch (see below) |
| **ExoMiner** (Valizadegan et al. 2022, NASA Ames) | Ensemble CNN over multiple diagnostic branches: global/local light-curve views, secondary eclipse, odd-even, centroid, difference-image | Per-branch + fused classification probability | Currently among the most capable automated vetters; used by NASA to vet/confirm large batches of new TESS candidates |
| **EEFN** (this project) | Cross-catalog stellar-parameter disagreement (TOI/TIC vs. Gaia DR3: T_eff, radius, distance), Gaia RUWE astrometric-binarity signal, transit-derived vs. Gaia-evolutionary stellar density self-consistency, plus a light-curve-shape DL branch | Evidence-consistency score (RF, real/trained) + health grade + alerts; DL classification (**synthetic-data-trained only** — see LIMITATIONS.md §1.7) | RF path is real and validated (E.1/E.2 above); DL path is a demonstrated architecture, not yet a validated classifier |

## Where EEFN's evidence overlaps with these tools, and where it doesn't

**Overlap**: EEFN's DL branch (global+local CNN views) is architecturally the same
concept as AstroNet's core approach — folded light-curve morphology classification.
This is the one place EEFN and the field's established light-curve vetters compete on
the same evidence. Here, EEFN currently loses that comparison outright: AstroNet and
ExoMiner are trained on tens of thousands of real, human-vetted Kepler/TESS light
curves; EEFN's DL branch is trained entirely on synthetic injected transits
(LIMITATIONS.md §1.7) and should not be treated as validated until it's retrained on
real MAST data (UPGRADE_PLAN.md F.6).

**No overlap — EEFN's distinguishing angle**: None of TRICERATOPS, Robovetter,
AstroNet, or ExoMiner check whether a TOI's *catalog record itself* is internally
consistent — whether the TESS pipeline's stellar parameters agree with Gaia DR3's,
whether Gaia flags the host as an unresolved binary (RUWE), or whether the
transit-implied stellar density matches the star's independently known evolutionary
density. TRICERATOPS gets close via its pixel-level "which star is this signal
actually on" analysis, but that's a photometric-blend question, not a
catalog-cross-match question — a real, isolated, well-behaved star with just an
implausible transit-depth-to-radius relationship (this pipeline's `is_unphysical_rp`
flag) wouldn't be caught by any of the four tools above, but is exactly what EEFN's
`density_discrepancy_sigma` and `derived_rp_diff` metrics are built to catch.

## Honest conclusion

EEFN's catalog-disagreement evidence is a **complement**, not a competitor, to
TRICERATOPS/AstroNet/ExoMiner. A working vetting pipeline gets the most value running
EEFN's catalog checks *alongside* light-curve-based statistical validation (TRICERATOPS
in particular, given its current TFOP adoption), not as a replacement for it. Claiming
EEFN's RF-based evidence-consistency score is a substitute for TRICERATOPS' FPP would
be overselling — they answer different questions (is this candidate's catalog record
self-consistent? vs. is this transit signal astrophysically real and on the target
star?). The honest, defensible claim is narrower and still real: EEFN surfaces a
specific, currently-unaddressed false-positive/false-confidence mode (catalog
disagreement) that the field's most-used vetting tools don't check.

## What a real empirical comparison would require (future work)

1. A shared target set of TOIs with published TRICERATOPS FPP values (many exist in
   TOI confirmation papers and the ExoFOP-TESS database) or ExoMiner scores (NASA has
   published bulk results for TESS sectors).
2. Correlate EEFN's `evidence_consistency_score`/`health_grade` against those published
   FPP/ExoMiner scores on the same targets — do they agree, and where do they diverge?
   Divergent cases are the most scientifically interesting (either EEFN catches
   something they miss, or vice versa).
3. This is real, tractable follow-up work — it does not require running the other
   tools locally, only fetching their already-published outputs for overlapping
   targets. Flagged here as a concrete next step, not attempted in this pass.
