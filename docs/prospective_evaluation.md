# Prospective evaluation: do the catalog flags anticipate false positives?

EEFN's pitch is that cheap catalog-hygiene flags can tell an observer which unresolved TOIs are
likely to be rejected, so scarce follow-up time goes elsewhere. Nothing measured so far shows that:
the model's scores are evaluated on candidates whose dispositions were already known when the model
was built (`backend/app/ml/honest_evaluation_report.json`). This is the test that can show it, set
up so it cannot be passed by accident or by tuning.

## Pre-registered hypothesis

> Among TOIs that are **unresolved** (TFOP disposition PC or APC) on the snapshot date, those with
> **at least one core catalog flag** are more likely to later be dispositioned **FP or FA** than those
> with none.

* **Core flags** (`app/science/flags.py`): `ruwe_likely_binary` (Gaia RUWE > 1.4), `unphysical_radius`
  (Gaia-radius-derived planet radius > 22 R_Earth), `density_inconsistent` (transit stellar density vs
  Gaia FLAME density outside the central 95% of confirmed planets), `teff_outlier` (TIC vs Gaia Teff
  differ by > 400 K), `radius_outlier` (TIC vs Gaia radius differ by > 30%).
* A flag is `None` ("could not check"), never `False`, when its inputs are missing. A candidate with
  no checkable core flag is excluded from the flagged-vs-clean comparison, not counted as clean.
* All thresholds are embedded in the snapshot file. **Changing a threshold means taking a new
  snapshot; an old snapshot is never re-scored.**

## How the snapshot is frozen

```bash
cd backend
python validation/scripts/prospective_snapshot.py --label first
```
It fetches the archive's **current** dispositions, keeps only TOIs that are still PC/APC (a candidate
resolved since the database's last sync is a known outcome, not a prediction), computes the flags,
writes `app/ml/prospective/snapshot_<date>_<label>.json` (never overwritten), and appends its SHA-256
to `app/ml/prospective/MANIFEST.json`. **Commit both files** so the timestamp is in version history.

The first snapshot (`snapshot_20261013_first.json`) holds 108 unresolved TOIs: 33 with at least one
core flag, 73 with none checkable-and-clean, 2 not checkable (389 more were already resolved and
excluded).

## How it is judged

```bash
python validation/scripts/prospective_evaluate.py snapshot_20261013_first.json
```
* It **refuses** to run if the snapshot's hash no longer matches the manifest.
* It compares current archive dispositions with the snapshot: CP/KP = planet, FP/FA = false positive;
  still-unresolved and withdrawn TOIs are reported but never counted as outcomes.
* It draws **no conclusion** until at least **60 candidates have resolved with at least 10 in each
  arm** (`app/science/prospective.py`). Before that it prints `TOO EARLY` and the progress.
* Once allowed, the verdict is `SUPPORTED` only if the 95% Newcombe interval for the risk
  difference (false-positive rate of flagged minus clean) lies entirely above zero **and** the
  one-sided Fisher exact p < 0.05; otherwise `NOT SUPPORTED`. Per-flag results, Wilson intervals and
  the share of all false positives that were flagged are reported alongside.

The pure logic is unit-tested on synthetic outcomes (an informative flag is SUPPORTED, a useless one
is NOT SUPPORTED, too few resolved candidates gives no conclusion at all).

## What the flags look like on already-labelled candidates (calibration, not the test)

On the 177 confirmed planets (CP/KP) and 203 false positives (FP/FA) in the project database:

| Flag | Fires on confirmed planets | Fires on false positives |
|---|---|---|
| RUWE > 1.4 | 3% | 35% |
| Teff outlier (> 400 K) | 3% | 23% |
| Unphysical radius | 1% | 10% |
| Radius outlier (> 30%) | 0% | 2% |
| Density outside the confirmed-planet 95% band | 6% (by construction) | 33% |

These show the flags *separate* labelled planets from labelled false positives, which is unsurprising:
those dispositions were assigned by reviewers who looked at RUWE and similar signals. The density
band was calibrated on the confirmed planets only; the other thresholds are literature values
(`app/science/flags.py`). **None of this is evidence for the pre-registered hypothesis**, which
concerns candidates whose outcome was not yet known.

## What would change the conclusion, and what this cannot show

* **Circularity is not removed.** TFOP reviewers also look at RUWE and Gaia neighbours. A flag that
  "predicts" a later FP may simply be one the reviewers acted on, in which case it adds no information
  they did not already have. The test therefore measures agreement with future dispositions; whether
  EEFN would have saved a *different* observation than the one the reviewers' own checks already
  avoided needs the FP's provenance (imaging, NEB check, RV), recorded where ExoFOP exposes it.
* **Small and slow.** 108 candidates, and TOIs take months to years to resolve; the first look is
  worth taking after ~6 months, and the guard will say so if it is too early.
* **Not a sample of all TOIs.** It is the subset the project ingested. Raising the ingestion limit
  and re-snapshotting (as a new label) widens it; it does not change this snapshot.
* **A flagged candidate that is later confirmed is a real failure** of the flag and is reported as
  such (`fp_rate_flagged` < 1), not silently dropped.
* A result of `NOT SUPPORTED` is a valid and useful outcome: it would mean the catalog flags do not
  anticipate dispositions beyond what reviewers already do, and the project's claim should shrink to
  "transparent provenance and hygiene flags", not "saves follow-up effort".
