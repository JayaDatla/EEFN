# Time-saved and completeness study (protocol, not yet run)

**Question.** For someone choosing TESS candidates to follow up, does EEFN reduce the time needed to
assemble the cross-catalog evidence, and does it make that evidence more or less complete than doing the
same checks by hand? (A reviewer asked for exactly this comparison. Nobody has published one for TOI vetting.)

**Status.** Design only. Nothing below has been run and no result exists. Fix this file before the first
participant starts; any later change is recorded as a deviation.

## Task

For each TOI, assemble the evidence needed to decide "worth a follow-up slot, or not". The pre-registered
checklist for one TOI is the same in both conditions:

1. Gaia DR3 RUWE of the host star.
2. Gaia stellar radius, and the planet radius recomputed from the transit depth.
3. Transit-derived stellar density and Gaia density (from period, duration, depth, Gaia mass and radius).
4. TOI-table Teff vs Gaia Teff.
5. TOI-table stellar radius vs Gaia radius.
6. Whether public ExoFOP-TESS follow-up notes or observations exist for the TOI (yes/no, not their content).
7. A go / no-go / unsure decision with a one-line reason.

## Conditions

- **A (own method).** The participant uses whatever they normally use (ExoFOP, the NASA Exoplanet Archive,
  Gaia archive, their own scripts). They may reuse scripts they already have; note that and its set-up time
  separately.
- **B (EEFN).** The participant uses the EEFN candidate page or CSV export.

## Design

- 3-5 participants (observers or experienced amateurs), each does both conditions. Order is counterbalanced
  across participants. Each participant gets two **different** sets of 10 TOIs, one per condition, so there
  is no learning from the first set; which set goes with which condition is also counterbalanced.
- Sets are drawn at random (seed recorded) from live TOIs, stratified: half have at least one EEFN core flag
  and half have none, with a mix of radius above and below 8 Earth radii and with and without Gaia
  parameters. The TOIs and seed are written down before recruiting.
- Time is measured per TOI from opening the target to writing the decision. Participants time themselves
  or are observed; either way it is recorded the same way. Set-up time (installing, learning the tool) is
  recorded separately and reported separately.

## Measures (all pre-registered)

| Measure | How |
|---|---|
| Time per TOI | seconds, per condition |
| Completeness | items 1-6 retrieved, out of 6, against a reference answer sheet computed from the catalogs by the team before the session |
| Accuracy | retrieved values within 1% of the reference (or within the rounding of the source) |
| Decision | go / no-go / unsure, with the reason; compared across conditions, not scored as right or wrong |
| Confidence | 1-5 rating after each set |
| Free text | what was missing, misleading, or slow |

## Analysis (fixed in advance)

- Paired by participant: median difference in time per TOI (A minus B) and in completeness, with a
  bootstrap 95% interval over participants and TOIs. With so few participants this is a feasibility study:
  report the intervals and the individual participants, and do not claim significance.
- Report completeness errors in both directions (EEFN missing something a participant found by hand, and the
  reverse). Report any check that participants called misleading.
- Report that EEFN's own reference answers come from the same catalogs it uses, so agreement with the
  reference is partly built in.

## What would count as "not useful"

Pre-registered, so it cannot be redefined afterwards: no median time saving, or a saving only for
participants who had no existing script, or completeness lower than by-hand. A result like that is
reported as it is and changes what the project says it is for.

## Ethics and practicalities

Participation is voluntary and unpaid; get consent in writing; store no personal data beyond a pseudonymous
participant ID; share the results back with participants; credit those who agree. Do not use proprietary
TFOP data in the task. Run the study only with people who understand EEFN is an unfinished student project.
