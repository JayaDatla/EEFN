# EEFN vs. Published Vetting Tools

**Status**: Methodology-level comparison, not an empirical benchmark. Revised 2026-10-13 after a literature review; the earlier version overstated EEFN's novelty and described a CNN branch that has since been retired.
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
| **EEFN** (this project) | TOI-table values, TOI-vs-Gaia DR3 disagreement (Teff, radius, distance), Gaia RUWE, 2MASS / Pan-STARRS colours, a stellar-density/duration check; plus a gradient-boosted vetter over physics features of the real light curve (odd/even, secondary eclipse, shape, implied radius) and a real-TPF centroid check | Evidence-consistency score (a TOI-table disposition prior), light-curve class probabilities (uncalibrated), centroid offset | Early. Tabular score: AUC 0.927 star-grouped, ~0.85 time-forward, cross-catalog features add ~+0.007 AUC over TOI columns. Vetter: 83% Kepler CV, 76% (n=50, 95% CI ~0.63-0.86) agreement with TFOP labels on TESS |

## Where EEFN's evidence overlaps with these tools, and where it doesn't

**Overlap**: EEFN's light-curve vetter competes with these tools on the same evidence (folded
light-curve morphology), and loses clearly: ExoMiner/ExoMiner++ train on tens of thousands of real
light curves and add centroid and difference-image evidence (ExoMiner++ reports PR-AUC ~0.97 on its own
TESS task -- not comparable to EEFN's numbers, which are on different labels and a far smaller set).
EEFN's vetter is a small gradient-boosted model over a few physics features, trained on 205 Kepler KOIs;
its value is that it is simple and inspectable, not that it is competitive.

**Where the catalog-consistency idea actually stands**: no published tool was found that scores
TOI-vs-Gaia stellar-parameter disagreement and trains it against TFOP dispositions (absence of search
hits -- weak evidence). But the pieces are not unaddressed elsewhere: ExoMiner++ takes Gaia RUWE and
TESS magnitude as inputs; LEO-vetter uses stellar radius for a size cut and catalog positions for its
centroid test; TRICERATOPS uses the TIC neighbours as blend scenarios; and TFOP reviewers already apply
Gaia RUWE and neighbour checks. Two further caveats from measurement and the literature: TIC-8 stellar
parameters are themselves computed from Gaia DR2, so TOI-minus-Gaia differences are largely method noise
rather than independent evidence; and in EEFN's own evaluation the cross-catalog features add only about
+0.007 AUC over the TOI table's columns under star-grouped CV and nothing under time-forward splits
(`backend/app/ml/honest_evaluation_report.json`). What is genuinely useful is the transparent flags
(RUWE, an implausible derived radius, a duration/density inconsistency) with their provenance, as a
pre-screen for TOI reviewers.

## Honest conclusion

EEFN is a **complement and pre-screen**, not a substitute for TRICERATOPS, ExoMiner, SPOC DV or TFOP
imaging, and it should not be described as detecting a failure mode the field misses. The defensible
claim is narrower: a cheap, transparent, light-curve-free audit of whether a TOI's host-star inputs look
trustworthy, with sourced flags and a full provenance trail. Whether that saves any follow-up effort has
not been measured; the test that would measure it (flag unresolved candidates now, compare with eventual
dispositions) is described in `docs/prospective_evaluation.md`.

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
