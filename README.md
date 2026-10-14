# EEFN — Exoplanet Evidence Fusion Network

A cross-catalog audit tool for TESS planet candidates. For each TESS Object of Interest (TOI) it
pulls the NASA Exoplanet Archive record, matches the host star to Gaia DR3 (plus 2MASS and
Pan-STARRS), and checks whether the catalogs agree with each other and with the transit itself.
Every number on screen traces back to a catalog, a rule, or a measured model score.

It does not confirm planets. Disposition labels in the training data were set by astronomers,
partly from the same Gaia signals used here, so the models partly reproduce human vetting.
Read [`LIMITATIONS.md`](LIMITATIONS.md) before relying on any output.

## What it gives you per candidate

**Rule-based catalog checks (no model).** Fixed thresholds, each shown with its value:

| Check | Flags when |
|---|---|
| RUWE (Gaia astrometric noise) | > 1.4 |
| Planet radius recomputed from depth and Gaia stellar radius | > 22 R⊕ |
| Transit-derived stellar density vs Gaia density | outside the central 95% of confirmed planets |
| Effective temperature, TOI vs Gaia | differs by > 400 K |
| Stellar radius, TOI vs Gaia | differs by > 30% |

A check that cannot run (missing data) is shown as unknown, never as passed. A clean result means
"no catalog red flags", not "planet".

**Model scores.**
- A LightGBM planet probability from the catalog features, shown as an A–F grade.
- A light-curve vetter on the real TESS SPOC light curve (odd/even depth, secondary eclipse, shape).
- Real TESS centroid offsets and APOGEE-2 spectroscopy, run nightly on a few candidates at a time.

## Measured performance

| Claim | Result | How it was measured |
|---|---|---|
| Planet probability | AUC 0.926 (95% CI 0.916–0.935) | star-grouped 5-fold CV, 2,667 labelled TOIs |
| Same, scoring later TOIs from earlier ones | AUC 0.84–0.88 | time-forward splits |
| Value of the cross-catalog features | +0.007 AUC over TOI-table columns alone | paired, star-bootstrap |
| Grade A is a false positive | 6.6% of the time (B 15%, C 39%, D 61%, F 94%) | star-grouped CV |
| Flagged TOIs vs unflagged | 39–43 points more often false positives | train on older TOIs, test on later TOIs of new stars |
| Light-curve vetter | 83% (±6) on Kepler; 76% agreement, AUC 0.81 on 50 TESS TOIs | star-grouped CV; TESS transfer check |
| Centroid offsets | 5 candidates measured, none flagged | one earlier "5.4σ" claim was retracted (re-measured 1.97σ) |

The flag result is retrospective and can be inflated because dispositions use the same evidence.
The unbiased test is frozen in
[`backend/app/ml/prospective/`](backend/app/ml/prospective) (108 unresolved TOIs, hash-registered
2026-10-13). It needs about six months of outcomes; see
[`docs/prospective_evaluation.md`](docs/prospective_evaluation.md).

Reports: `backend/app/ml/honest_evaluation_report.json`, `split_validation_report.json`,
`lightcurve_vetter_report.json`, `tess_transfer_report.json`.

## Run it

Requires Python 3.13, Node 18+, and Redis for background jobs. See [`STARTUP.md`](STARTUP.md) for the
full local setup.

```bash
# backend
cd backend
pip install -r requirements.txt
alembic upgrade head
python -m uvicorn main:app --host 127.0.0.1 --port 8000   # docs at /docs

# frontend (another terminal)
cd frontend
npm install
npm run dev                                                # http://localhost:3000
```

The frontend reads `NEXT_PUBLIC_API_URL`, defaulting to `http://127.0.0.1:8000`.

Nightly enrichment (spectroscopy 02:00, centroids 03:00, light-curve vetting 05:00) runs in the worker:

```bash
cd backend
arq app.worker.WorkerSettings
```

Fill the database from NASA/Gaia/2MASS/Pan-STARRS with `eefn sync --limit 100` after
`pip install -e backend`. The CLI also has `eefn audit --toi 1017.01` and
`eefn export --format csv|json|votable`.

Set `API_KEY` before exposing the API to anyone else; without it the write endpoints are open.

## Reproduce the numbers

```bash
python reproduce_results.py                              # recomputes the tabular metrics, exits non-zero on mismatch
cd backend
python validation/scripts/honest_evaluation.py           # star-grouped and time-forward evaluation
python validation/scripts/split_validation.py            # grade and flag results on held-out splits
python validation/scripts/prospective_evaluate.py snapshot_20261013_first.json   # after ~6 months
pytest tests/
```

Retraining the models: `python validation/scripts/train_and_serialize_model.py` (tabular) and
`backend/validation/scripts/train_lightcurve_vetter.py` (needs MAST network access).

## Layout

```
backend/    FastAPI, SQLAlchemy/Alembic, Arq jobs, models and science code (app/science, app/ml, app/pipeline)
frontend/   Next.js 14 app
validation/ training data and the tabular-model scripts
docs/       design notes, evaluation protocol, tool comparison
```

Other interfaces: `GET /api/v1/resolve?id=` maps TOI, TIC and Gaia IDs; `GET /api/v1/candidates/export`
writes a VOTable that opens in TOPCAT; `WEBHOOK_URLS` posts when a pipeline run finishes.
[`DATA_FLOW.md`](DATA_FLOW.md) describes the pipeline and schema;
[`docs/TOOL_COMPARISON.md`](docs/TOOL_COMPARISON.md) compares it with TRICERATOPS, ExoMiner and others.

## Status

Research prototype. No astronomer has used it on a real target list yet; that would be worth more than
any remaining code change. Open items: ingest SPOC DV centroid offsets, key the cross-match on Gaia ID,
add a Gaia DR4 adapter, and compare against published TRICERATOPS/ExoMiner values.

## Contributing and license

[`CONTRIBUTING.md`](CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). BSD-3-Clause, see
[`LICENSE`](LICENSE).
