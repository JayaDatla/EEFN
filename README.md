# EEFN — Exoplanet Evidence Fusion Network

EEFN is an automated cross-catalog evidence auditor for transiting planet candidates. It
ingests a TESS Object of Interest (TOI) from the NASA Exoplanet Archive, cross-matches it
against Gaia DR3, and tells an observer — with a full audit trail — whether that
candidate's catalog record is internally consistent enough to be worth scarce follow-up
telescope time.

It is **not** an "AI confirms exoplanets" tool. Every disposition label in the training
data was already assigned by human astronomers, in part using the same Gaia signals
(RUWE, distance) EEFN's models are trained on — so a model trained on them partly learns
to reproduce human categorization, not to independently discover planets. See
[`LIMITATIONS.md`](LIMITATIONS.md) §1.1 for the full discussion of this, and every other
disclosed limitation.

## What it actually does

For each candidate, EEFN:
- Cross-matches NASA/TOI, Gaia DR3 Source, and Gaia DR3 Astrophysical Parameters catalogs.
- Computes catalog-disagreement metrics (temperature, radius, distance mismatches; RUWE
  astrometric-binary signal; a transit-depth-derived planet radius checked against the
  catalog value).
- Runs a trained Random Forest evidence-consistency classifier over the real feature
  vector — see `backend/app/ml/predict.py` and `backend/app/ml/model_metrics.json` for
  the actual held-out evaluation metrics.
- Runs a 4-branch deep learning model (`DeepExoFusionNet`) as a demonstration pathway
  over simulated light curves — see [`LIMITATIONS.md`](LIMITATIONS.md) §1.5, §1.7 for what
  this model has and hasn't actually been trained/validated on before you rely on it.
- Computes one unified evidence health score (0-100, letter grade A-F) — see
  `backend/app/science/health.py` for the single formula every code path uses.
- Surfaces everything through a FastAPI backend and a Next.js frontend, with alerts that
  explain *why* a candidate was flagged, not just that it was.

## Status

This project is under active development against
[`UPGRADE_PLAN.md`](UPGRADE_PLAN.md), a phased plan to take EEFN from a working
prototype to a tool a real observer would trust on a Tuesday night. Read that file for
the full list of known issues, what's already fixed, and what's still in progress. Read
[`LIMITATIONS.md`](LIMITATIONS.md) before treating any output as more than it is.

## The highest-leverage thing left isn't code

Per `UPGRADE_PLAN.md` E.5: one TFOP-affiliated astronomer using EEFN for a real
observing season is worth more to this project's credibility than any remaining
engineering task. This is a relationship/outreach step for a human to pursue, not
something to automate — flagged here prominently rather than silently skipped. If
you're an astronomer (or know one) working TESS follow-up who'd try this against a
real target list, that's the single most valuable next contribution.

## Architecture

See [`DATA_FLOW.md`](DATA_FLOW.md) for the full ingestion/fusion/inference pipeline,
database schema, and feature-engineering formulas, with diagrams.

Short version: FastAPI + SQLAlchemy backend (SQLite or Postgres, Alembic-migrated) in
`backend/`, Arq/Redis job queue for ingestion runs, Next.js 14 + React 18 + TypeScript
frontend in `frontend/`, scikit-learn Random Forest + PyTorch deep learning models in
`backend/app/ml/`. See [`docs/TOOL_COMPARISON.md`](docs/TOOL_COMPARISON.md) for how
EEFN's catalog-disagreement approach relates to published vetting tools
(TRICERATOPS, AstroNet, ExoMiner, Robovetter).

## Interoperability

Per `UPGRADE_PLAN.md` Part G ("meet observers where they already work" — a standalone
dashboard is an adoption blocker):
- **VOTable export**: `GET /api/v1/candidates/export` or `eefn export --format votable`
  — a real, standards-compliant VOTable (verified by round-tripping through astropy's
  own parser) that opens directly in TOPCAT/Aladin or loads via `astroquery`.
- **Identifier resolution**: `GET /api/v1/resolve?id=...` accepts a TOI ID, TIC ID, or
  Gaia DR3 `source_id` in any common format and returns the other two — never hand-
  translate between them.
- **Webhooks**: set `WEBHOOK_URLS` (comma-separated) to get a push notification when a
  pipeline run finishes, so a TFOP triage channel doesn't need to poll. The payload
  includes a top-level `text` field, so pointing it directly at a Slack incoming-
  webhook URL renders sensibly with no Slack-specific integration needed.
- **Python client**: `pip install -e backend` installs the `eefn` package/CLI (see
  Quickstart below) — this *is* the "astroquery-style package" the plan asks for.

**Not implemented, and deliberately not attempted as unilateral code**: ExoFOP-TESS
structured comments (the plan itself says this "needs coordination with ExoFOP
maintainers" — there's no public write API to integrate against without that,
and building one without their buy-in wouldn't be usable). A Zenodo DOI per release is
a release-process step for whoever cuts a release, not something to code.

## Quickstart

### Backend
```bash
cd backend
pip install -r requirements.txt
alembic upgrade head   # schema is Alembic-managed, not auto-created (see D.1)
uvicorn main:app --reload
```
The API comes up at `http://127.0.0.1:8000`; interactive docs at `/docs`. Defaults to a
local SQLite file; set `DATABASE_URL` to a Postgres DSN for multi-writer use (a
`postgres` service is already defined in `docker-compose.yml`).

`POST /pipeline/run` and the resolution-override endpoint need a running Redis + Arq
worker (see D.2):
```bash
docker compose up -d redis          # or run your own Redis on REDIS_URL
cd backend
arq app.worker.WorkerSettings       # in a separate terminal
```
Set `API_KEY` in the environment before exposing the API anywhere reachable by anyone
else — without it, `/pipeline/run` and the resolution-override endpoint are
unauthenticated (a loud warning prints at startup if it's unset; see D.3).

EEFN also installs as a Python package/CLI:
```bash
pip install -e backend
eefn audit --toi 1017.01
eefn sync --limit 100
eefn export --format csv        # also: json, votable
```

Run the test suite:
```bash
cd backend
pytest tests/
```

To (re)train the Random Forest and write real evaluation-metrics/calibration
artifacts (accuracy/ROC-AUC/F1, reliability diagram, Brier score):
```bash
python validation/scripts/train_and_serialize_model.py
```

To run the label-leakage ablation studies (see LIMITATIONS.md §1.1):
```bash
python validation/scripts/leakage_ablation.py
python validation/scripts/leakage_rv_confirmed_holdout.py
```

To (re)train the deep learning model against the current 4-branch architecture:
```bash
cd backend
python -m app.ml.train_deep_learning
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Comes up at `http://localhost:3000`. Requires the backend running at
`http://127.0.0.1:8000` — the frontend does not yet read a configurable API URL
(hardcoded in ~19 places; see `UPGRADE_PLAN.md` A.14/H.5, not yet fixed), so it currently
only works against a backend on localhost.

### Docker
```bash
docker-compose up
```

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the development setup, what will and
won't be merged, and code style. This project follows the
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## License

BSD-3-Clause — see [`LICENSE`](LICENSE).
