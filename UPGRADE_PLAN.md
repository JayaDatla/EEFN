# EEFN — Master Upgrade Plan

**Status:** Approved for execution.
**Purpose:** This is a complete, self-contained specification for turning EEFN (Exoplanet Evidence
Fusion Network) from an impressive-looking prototype into a scientifically correct tool that real
exoplanet observers (TFOP groups, independent astronomers, observatory schedulers) actually rely
on — backend, ML pipeline, and a full frontend redesign.

---

## HOW TO USE THIS DOCUMENT (read this first)

You are picking this up cold, in a fresh session, with no memory of how it was written. Everything
you need is in this file. Do not skip this section.

1. **Read the entire document before writing any code.** Part A is a dossier of verified findings
   — bugs that were confirmed by actually reading and, where noted, *running* the code, not
   guessed at. Trust it; you don't need to re-derive it, but spot-check anything before relying on
   it for a destructive action.
2. **Work in phase order.** Phase 0 is a hard blocker — nothing in Phase 3, 4, or 5 should start
   until Phase 0 is done, because every later phase either builds on the ML pipeline or the API
   surface Phase 0 fixes. Phase 1 (backend architecture) and Phase 5 (frontend redesign) can run in
   parallel once Phase 0 is done. See the sequencing table near the end for the full ordering.
3. **Use TaskCreate/TaskUpdate to track your progress through this plan.** Create one task per
   numbered subsection (0.1, 0.2, ... 5.4, ...) so progress survives context compaction. Mark each
   complete only when its Definition of Done (Part M) is actually satisfied.
4. **Never fabricate.** This entire plan exists because the current codebase fabricates numbers
   (hardcoded "confirmation probabilities," fake feature importances, static "model metrics",
   silent fallback demo data rendered as if real). Do not reproduce this pattern anywhere you touch.
   If real data isn't available, show an explicit "unavailable" state — never a plausible-looking
   substitute.
5. **Test and verify before claiming done.** Backend: write/run pytest for anything you fix,
   especially regression tests for the specific bugs in Part A (e.g. "inference output must not
   change when `disposition` is mutated"). Frontend: actually start the dev server and look at the
   pages in a browser (use the `run` skill if available) — do not declare frontend work finished
   based on a successful build alone.
6. **Ask before anything irreversible or externally visible**: deploying, pushing to a remote,
   force operations, deleting data, or emailing/posting anywhere. Everything else in this plan is
   pre-approved local work — proceed without re-confirming each item with the user.
7. **This is a big plan. It's fine to take a long time and multiple sessions.** Quality and
   correctness matter more than speed. When in doubt about a design decision not covered here,
   prefer the option that a working astronomer would trust more, per the closing "one-line test."

---

# PART A — VERIFIED GROUND TRUTH (evidence dossier)

Everything in this section was confirmed by reading the actual code (file:line references given)
or, where marked **[RAN]**, by executing it. Do not treat these as hypotheses.

### A.1 The Random Forest is never actually invoked

`backend/app/ml/predict.py` loads a pickled RF model + imputer in `__init__` (lines 17-25) but
`predict_confirmation()` (lines 36-159) never calls `self.model.predict()` or
`self.model.predict_proba()`. Instead:

```python
# predict.py:96-110
if is_unphysical:
    prob_confirmed = 0.035
    priority_score = 0.02
else:
    if candidate_obj and candidate_obj.disposition in ['CP', 'KP']:
        prob_confirmed = 0.945
        priority_score = 0.92
    elif candidate_obj and candidate_obj.disposition == 'FP':
        prob_confirmed = 0.042
        priority_score = 0.05
    else:
        prob_confirmed = 0.842 if RUWE <= 1.4 else 0.420
        priority_score = 0.78 if RUWE <= 1.4 else 0.35
```

For any candidate with a known disposition, the "confirmation probability" is a direct read of the
label it is supposedly predicting. This is not label leakage in the statistical sense — it is a
hardcoded lookup of the answer key, dressed as a percentage.

`top_contrib` (lines 112-118) — the "feature contribution" dict returned to the frontend as
`feature_importance` — is likewise fabricated per call from a few if/else rules, not derived from
the model.

### A.2 The deep learning model runs on random, untrained weights — **[RAN, confirmed]**

`backend/app/ml/model_weights.pth` (12MB) exists and was genuinely trained once — but against an
**older, incompatible architecture**. Loading it against the current `DeepExoFusionNet`
(`deep_learning_pipeline.py:119-163`) fails:

```
RuntimeError: Error(s) in loading state_dict for DeepExoFusionNet:
  size mismatch for metadata_branch.fc1.weight: checkpoint [32, 8] vs current model [32, 16]
  size mismatch for fc1.weight: checkpoint [128, 448] vs current model [128, 576]
```

The checkpoint has **no `centroid_branch` weights at all** (verified: `any('centroid_branch' in k
for k in checkpoint.keys())` → `False`), and its metadata layer was sized for 8 features, not the
current model's 16. The old checkpoint corresponds to a 3-branch net (global + local + metadata,
fusion dim 256+128+64=448); the current code is a 4-branch net (+ centroid, fusion dim
256+128+128+64=576).

`deep_learning_pipeline.py:182-187` wraps the load in a bare `try/except Exception`, prints one
console line (`"Loaded ExoFusion-Net v2 with initialized architecture (...)"`), and **silently
continues with a freshly random-initialized network**. Nothing in the API response, logs (beyond
stdout), or UI indicates this. Every DL classification, confidence, and "integrated gradients"
value currently served is noise from an untrained model.

**Additional finding**: `backend/app/ml/train_deep_learning.py` never trains on real TESS light
curves. Every training sample is generated by
`transit_pipeline.generate_simulated_lightcurve()` — synthetic injected transits, not real MAST
data. So even a correctly-loading checkpoint would never have seen a real light curve.

### A.3 Two health-score implementations that disagree

| Term | `ingest.py:234-242` | `alert_engine.py:132-204` |
|---|---|---|
| Teff mismatch | `/20`, cap 25 | `/20`, cap 20 |
| Radius mismatch | `/0.05`, cap 25 | `/0.05`, cap 20 |
| RUWE > 1.4 | −20 | −15 |
| Unphysical Rp | −30 | −25 |
| Distance mismatch | *absent* | `/10`, cap 10 |
| Completeness | *absent* | `(1 − score) × 20` |
| `query_failed` | −15 | *absent* |
| "D" grade floor | ≥50 | ≥60 |

Same candidate → different grade depending which code path computed it.

### A.4 The transit-derived stellar density formula is dimensionally wrong

`ingest.py:215`:
```python
density_transit = 32.0/(6.674e-8*math.pi) * ((trandurh*3600)**(-3)) / ((trandep*1e-6)**0.75)
```
The correct relation (Seager & Mallén-Ornelas 2003) is ρ⋆ ∝ P/(G·T14³) — it requires the **orbital
period**, which never appears in this function. Dimensional analysis confirms the expression does
not resolve to g/cm³. `density_discrepancy_sigma` (used elsewhere as a real signal) is therefore
comparing a real Gaia-evolutionary density against a physically meaningless number, and its "sigma"
denominator (`0.3`) is a hardcoded constant, not a propagated uncertainty.

### A.5 The "unphysical radius" veto is a hard override, not a signal

`predict.py:93,96-99`, `deep_learning_pipeline.py:291-299`, `alert_engine.py:27-30` all use a
22 R⊕ cutoff, and in the DL path it **overwrites the network's output entirely**
(`probabilities[0] = 0.02; probabilities[1] = 0.95`). Radius alone cannot separate an inflated hot
Jupiter from a low-mass M-dwarf (both can be ~1 R_Jup due to electron degeneracy pressure) — a hard
veto here will misclassify real inflated giants, which is exactly the kind of error a working
astronomer will notice immediately and stop trusting the tool over.

### A.6 Missing data silently becomes "clean" evidence

- `deep_learning_pipeline.py:237-240`: missing centroid data → `np.zeros(201)`, read by the network
  as "the star's center of light did not move," i.e. **positive evidence against a background
  binary** — for a signal that was never measured.
- `predict.py:87,109`: missing RUWE → defaults to `1.0` ("definitely single star").
- This pattern will get worse, not better, as more catalogs are added (Phase 3), because more
  catalogs means more per-candidate partial coverage, and every one of today's defaults quietly
  converts "unknown" into "looks fine."

### A.7 Two disagreeing "confirmation probability"-shaped fields, one dishonest name

`confirmation_probability` is not a confirmation of anything — see A.1. The name itself invites
misuse by anyone who doesn't read the code.

### A.8 Static "model metrics" presented as measured performance

`endpoints.py:236-250` (`get_model_metrics`) returns hardcoded
`accuracy: 0.8448, roc_auc: 0.9154, f1_score: 0.8460` with no connection to any actual evaluation
run. The frontend `predictions/page.tsx` renders these as if live.

### A.9 Background pipeline task uses a session that's already closed

`endpoints.py:222-233`:
```python
@router.post("/pipeline/run")
def run_pipeline(background_tasks: BackgroundTasks, limit: int = Query(...), db: Session = Depends(get_db)):
    background_tasks.add_task(ingest_and_fuse_data, db, limit)
```
`db` comes from `Depends(get_db)`, whose generator closes the session in a `finally` block the
moment the HTTP response is returned (`session.py:17-22`). The background task then runs against a
closed SQLAlchemy session. This is a live bug, not theoretical — reproduce by hitting
`/pipeline/run` and watching it fail once the request returns before the task's first DB write.

### A.10 Ingestion never updates existing records

In `ingest.py`, `HostStar`, `ExoplanetCandidate`, and `AgreementMetrics` are only ever created
inside `if not star:` / `if not cand:` / `if not metrics:` guards — there is no `else` branch that
refreshes an existing row. Re-running the pipeline against updated NASA/Gaia data changes nothing
for targets already in the DB. A TOI whose disposition has since flipped PC→FP stays wrong
indefinitely. `completeness_score` is also hardcoded to `1.0` (`ingest.py:283`) regardless of how
many fields are actually populated.

### A.11 Dependencies don't match imports

`backend/requirements.txt` has no `torch`, yet `deep_learning_pipeline.py` imports it at module
scope and is imported by `endpoints.py`. A clean-environment `pip install -r requirements.txt`
followed by starting the app will fail. `neo4j` is declared but its usage should be verified (grep
found no clear live usage at time of writing — confirm before removing).

### A.12 No license, no README, broken CI

- No `LICENSE` file at repo root — legally blocks any institution from using the code at all.
- No root `README.md`.
- `.github/workflows/ci-cd.yml` sets `python-node: '3.11'` under `actions/setup-python`, which
  expects `python-version` — the key is wrong and the action does not configure Python as intended.

### A.13 The 7-catalog "v2" pipeline is 3/7 live, 2/7 portable, 2/7 never real

Documented in `project_dump/EXOFUSION_NET_V2_PROPOSAL.md` and `project_dump/data_expansion_report.md`.
The seven catalogs: NASA Exoplanet Archive/TOI, Gaia DR3 Source, Gaia DR3 AstroParams, 2MASS,
Pan-STARRS, spectroscopy (APOGEE-2S), MAST TESS FITS (light curve + centroid).

- **Live in `backend/app/pipeline/ingest.py` today**: NASA/TOI, Gaia Source, Gaia AstroParams (3/7).
- **Portable almost as-is**: `scratch/download_real_sample_data.py:80-110` has real, working CDS
  X-Match calls for 2MASS (`vizier:II/246/out`) and Pan-STARRS (`vizier:II/349/ps1`), using the
  exact same request pattern already live for Gaia.
- **Never actually built, despite docs implying otherwise**: in that same script, the spectroscopy
  sample (`:112-128`) is a hardcoded Python dict, and the "TESS FITS" sample (`:130-160`) is
  `np.random`-generated noise, not a real MAST download. No `astroquery`/`lightkurve` dependency
  exists anywhere in the repo.
- **The schema and DL model architecture are already built for all 7** (`HostStar` has
  `j/h/k_mag`, `g/r/i/z/y_mag`, `teff_spec`, `fe_h`, `alpha_fe`; `DeepExoFusionNet` has a real
  `CentroidSpatialCNN` branch) — they're just never fed by live ingestion. The only place these
  fields are populated today is `backend/seed_db.py`, which hardcodes plausible values directly in
  Python (no API calls). **Anything currently visible in the DB or frontend for these fields is
  seed/demo data, not live ingestion.**

### A.14 Frontend cannot be deployed and can silently lie

- `http://127.0.0.1:8000` is hardcoded in **19 places across 11 files**
  (`admin/page.tsx`, `ai-analysis/page.tsx` ×2, `candidates/page.tsx`, `candidates/[id]/page.tsx`
  ×5, `compare/page.tsx` ×3, `fusion/page.tsx`, `graph/page.tsx` ×2, `page.tsx`,
  `predictions/page.tsx`, `TelemetryBar.tsx`). No environment-based API URL exists. The app cannot
  be deployed to any environment other than "backend on localhost:8000" today.
- `candidates/page.tsx:26-31` defines a hardcoded `fallback` array of invented candidates.
  `candidates/page.tsx:38-50`'s `load()` catches fetch failure with `console.warn(...)` and leaves
  the fallback array rendered **with no visual indication it isn't real data**. A deployed instance
  with a down/unreachable backend silently shows fabricated science to whoever opens it.
- That fallback data is internally inconsistent, which is its own tell: `TOI-1020.01` has
  `disposition: "CP"` (confirmed planet) and `confirmation_probability: .885`, but
  `health_score: 44.2, health_grade: "F"` — a "confirmed planet" graded F.

### A.15 Frontend is a demo-quality showcase, not an instrument (design-level finding)

Read directly from `frontend/src/app/globals.css:1` (file is authored as one dense unformatted
line, not build-minified):

- A decorative animated background exists behind **every page**: a radial-gradient "nebula" plus a
  dot-grid "starfield" (`body:before`/`body:after`), pure decoration that competes with the data
  sitting on top of it.
- Every card/panel (`.scientific-metric`, `.surface-card`, `.glass-panel`) uses a translucent
  gradient fill plus `backdrop-filter: blur(18px)` — glassmorphism applied uniformly regardless of
  whether the element is actually a floating overlay.
- Decorative glow effects with no functional purpose: a status dot has
  `box-shadow: 0 0 10px #63d6b0`; stat cards have a faint decorative circle outline stamped in the
  corner (`.scientific-metric:after`) purely for visual flourish.
- Single dark theme only. No light/day theme, no reduced-motion handling, no verified contrast
  pass. Status is color-coded (`.confidence-badge.good/watch/risk`) without a redundant non-color
  signal in several call sites.
- No shared design-token file — colors are hardcoded ad hoc as hex/rgba throughout components and
  in this CSS file, rather than referencing a single source of truth.
- Three separate charting approaches in the dependency graph (`chart.js`+`react-chartjs-2`,
  `recharts`, and `three.js` for the galaxy view) plus `framer-motion`, with no consistent visual
  language between them.
- `src/app/components/` and `src/components/` both exist as component directories — duplicated
  location, not a duplicated component, but still a sign of drift.
- Several page files are 600+ lines (`graph/page.tsx` 773, `ai-analysis/page.tsx` 645,
  `demo/page.tsx` and `showcase/page.tsx` 615 each) mixing data-fetching, business logic, and
  markup in one file.

This is the concrete basis for the Phase 5 redesign (Part H) — treat every bullet above as a defect
to eliminate, not a style preference to debate.

---

# PART B — POSITIONING (read before writing any copy, UI text, or docs)

The current framing — "AI confirms exoplanets" — is not defensible: labels come from human
astronomers who already used Gaia RUWE/distance to classify candidates, so a model trained on them
partly learns to reproduce human categorization, not to independently confirm planets (see
`LIMITATIONS.md` §1.1, and A.1/A.2 above for how badly the current implementation compounds this).

**The reframing to use everywhere — API field names, UI copy, docs, alerts:**

> EEFN is an automated cross-catalog evidence auditor for transiting planet candidates. It tells an
> observer, with a full audit trail, whether a TOI's catalog record is internally consistent enough
> to be worth scarce follow-up telescope time.

Concrete consequence: rename `confirmation_probability` to something honest
(`evidence_consistency_score` or `fp_risk_score` — pick one and use it consistently in DB column,
API field, and UI label) across the whole stack as part of Phase 0/1. Never present a number the
pipeline didn't actually compute from real inputs.

---

# PART C — PHASE 0: CORRECTNESS AND HONESTY (blocking — do this first, entirely)

Nothing here is polish. Each item is something a reviewing astronomer or engineer would find within
an hour of looking, and each would individually end EEFN's credibility with that person.

### C.1 Make the Random Forest actually run (fixes A.1)
- In `predict.py`, build the real feature vector matching `feature_names` from the saved
  artifacts (`derived_rp_diff_rel`, `teff_diff`, etc. — see `DATA_FLOW.md` §5 for the 25-feature
  layout as a reference, but verify against `artifacts["features"]` at runtime, don't hardcode a
  list that can drift from the pickle).
- Call `self.imputer.transform(...)` then `self.model.predict_proba(...)`.
- Delete every branch that reads `candidate_obj.disposition` to set the output probability.
- Add a regression test: construct two identical feature vectors differing only in the DB row's
  `disposition`, assert the returned probability is identical. This specific test prevents this
  exact bug class from returning.

### C.2 Fix or retrain the deep learning model (fixes A.2)
- First, make the failure loud: change the bare `try/except Exception` around
  `load_state_dict` to log an error-level message and set an explicit `self.loaded = False` /
  `self.degraded = True` flag that propagates into every API response using this engine
  (`"model_status": "untrained_fallback"` or similar) and into the UI (visible badge, not buried).
  **Never again allow a model to silently serve random-weight output as if it were trained.**
- Then retrain properly: `train_deep_learning.py` must build the *current* 4-branch, 16-feature
  input shape (matching `deep_learning_pipeline.py`'s actual `DeepExoFusionNet` and the
  `metadata_vector` construction in `vet_candidate()`), not the old 8-feature/3-branch shape.
- Until real centroid data exists (Phase F), the centroid branch must be trained with the same
  missing-data masking strategy described in Part F, not silently-zero inputs, or it will bake in
  the exact "missing = clean" bias described in A.6.
- Add a startup contract check: attempt `load_state_dict(strict=True)`; if it fails, refuse silent
  fallback — either block startup with a clear error, or start in an explicitly-degraded mode that
  is visible end-to-end (API + UI). Store an architecture hash/version string alongside the weights
  file and compare it before loading, so a mismatched checkpoint is caught before `load_state_dict`
  is even attempted.
- Longer-term (can slip into Phase F if needed): retrain on real MAST light curves, not only
  `transit_pipeline.generate_simulated_lightcurve()` output.

### C.3 Unify the health score (fixes A.3)
- Create `backend/app/science/health.py` exporting one pure function, e.g.
  `compute_health_score(metrics: AgreementMetrics, candidate: ExoplanetCandidate) -> HealthResult`,
  versioned (`HEALTH_SCORE_VERSION = "1.1.0"`), with the full term table (teff, radius, distance,
  RUWE, unphysical-radius, completeness, query_failed) reconciled into one set of weights/caps —
  pick the more complete `alert_engine.py` formula as the base (it already includes distance and
  completeness terms `ingest.py` is missing) and add `ingest.py`'s `query_failed` term to it.
- Both `ingest.py` and `alert_engine.py` import and call this one function. Delete the duplicate
  inline logic in both places.
- Store `health_score_version` on `ExoplanetCandidate` so historical scores remain interpretable
  after the formula changes again later.
- Add golden-file tests: fixed input → fixed expected output, so any future formula edit is a
  deliberate, visible diff.

### C.4 Fix the stellar density formula (fixes A.4)
- Reimplement `density_transit` from Seager & Mallén-Ornelas (2003), including `pl_orbper`.
  Verify units resolve to g/cm³ with an explicit dimensional-analysis comment or a unit test using
  `astropy.units`.
- Validate against known systems with published values (e.g. TRAPPIST-1 system planets, or any
  well-characterized target already in the seed data) — assert computed density is within a
  reasonable tolerance of the literature value.
- Replace the hardcoded `/0.3` sigma denominator with a real propagated uncertainty from the input
  error columns already being fetched (`st_tefferr1/2`, `st_raderr1/2`, `b_Rad`/`B_Rad`, etc.).

### C.5 Soften the unphysical-radius veto (fixes A.5)
- Change from a hard override (`probabilities[0]=0.02` etc.) to a weighted input/flag: still raise
  the alert (it's a legitimate, valuable signal), but let it influence rather than replace the
  model's output, and incorporate stellar density/mass context where available rather than radius
  alone.

### C.6 Stop treating missing data as clean data (fixes A.6)
- Introduce an explicit "field present" companion signal wherever a physical default is currently
  substituted for `None` (RUWE, centroid arrays, any metadata feature). At minimum this means the
  model/rule inputs must be able to distinguish "RUWE unmeasured" from "RUWE = 1.0 measured"; do
  not silently conflate them.
- This is foundational for Part F (model pipeline architecture) — do the plumbing for it now even
  if the richer tiered-model consumption of it lands later.

### C.7 Rename the dishonestly-named field (fixes A.7, ties to Part B)
- Pick one name (`evidence_consistency_score` recommended) and rename consistently: DB column,
  Pydantic schema, API response field, and every frontend reference. Provide a one-time migration;
  do not leave both names live "for compatibility" — this project has no external API consumers yet
  to break.

### C.8 Serve real model metrics (fixes A.8)
- `get_model_metrics()` must read from an artifact written by the actual training/evaluation run
  (JSON file alongside the pickle, containing metrics, dataset hash, model version, evaluation
  date) — never a hardcoded dict in the endpoint.

### C.9 Fix the background task's DB session (fixes A.9)
- Minimum fix: have the task function open and close its own `SessionLocal()` rather than reusing
  the request-scoped session.
- Proper fix: this is superseded by Phase D.2 (real task queue) — if D.2 is being done in the same
  pass, do that instead of the minimum fix.

### C.10 Make ingestion actually refresh existing records (fixes A.10)
- Replace the create-only guards with real upsert logic: fetch-or-create, then update mutable
  fields (disposition, stellar parameters, transit parameters, computed metrics) on every run, with
  change detection so `MeasurementHistory` gets a new row only when a value actually changed.
- Compute `completeness_score` from actual non-null field coverage instead of hardcoding `1.0`.

### C.11 Fix dependencies (fixes A.11)
- Add `torch` (and its actual pinned version) to `requirements.txt`. Split into
  `requirements.txt` (base API), `requirements-ml.txt` (torch/sklearn/pandas heavy deps),
  `requirements-dev.txt` (pytest, linters) if that keeps the base API image lean — decide based on
  deployment needs in Phase D.
- Confirm whether `neo4j` is used anywhere at runtime; remove the dependency and config if not.

### C.12 Add LICENSE, README, fix CI (fixes A.12)
- Add a `LICENSE` file — MIT or BSD-3-Clause (BSD-3 matches the astropy/astronomy ecosystem norm).
  **Confirm the choice with the user before adding** — licensing is a real decision, not a default
  to silently pick.
- Add a root `README.md`: what EEFN is (using the Part B framing), quickstart, architecture
  pointer to `DATA_FLOW.md`, current status/limitations pointer to `LIMITATIONS.md`, license.
- Fix `.github/workflows/ci-cd.yml`: `python-node: '3.11'` → `python-version: '3.11'`. Add a job
  running the regression tests from C.1/C.2/C.3. Confirm the whole workflow actually passes green
  before moving on.

**Phase 0 exit criteria (all must be true):**
- [x] No code path invents a number not derived from real inputs or a real trained model.
- [x] No two code paths compute the same quantity with different formulas.
- [x] A clean-environment `pip install -r requirements.txt` + app start succeeds with no import
      errors.
- [x] The DL engine either loads an architecture-matched trained checkpoint, or visibly reports
      degraded/untrained status everywhere its output is used — never silently.
- [x] Re-running ingestion against an already-populated DB updates existing records.
- [x] `LICENSE`, `README.md` exist; CI is green.
- [x] Regression tests exist for C.1 (disposition-invariance) and C.3 (health score golden file).

---

# PART D — PHASE 1: BACKEND ARCHITECTURE

### D.1 Data layer
- Move to **PostgreSQL** as the primary datastore (R-2 from the earlier board-review pass this plan
  builds on). `models.py` already imports `sqlalchemy.dialects.postgresql.UUID` while `config.py`
  defaults to SQLite — before assuming this "just works," verify current UUID round-tripping under
  SQLite, then switch to a dialect-agnostic UUID type (SQLAlchemy 2.0's `sqlalchemy.types.Uuid`) so
  local SQLite dev still works alongside Postgres in production.
- Add **Alembic** migrations; stop relying on `Base.metadata.create_all()` in `main.py:10` as the
  schema management strategy.
- Add indexes on `toi_id`, `tic_id`, `disposition`, `health_grade` (all filtered/sorted on
  today, none indexed beyond uniqueness constraints).
- Make `MeasurementHistory` a real provenance ledger: every ingested value should get a row with
  source catalog, catalog version, query timestamp, and uncertainty — this table exists but
  ingestion doesn't populate it today. This *is* the product's core trust mechanism; treat it as
  first-class, not an afterthought table.

### D.2 Ingestion and job execution
- Replace `BackgroundTasks` with a real worker (Celery+Redis, or a lighter option like
  Arq/Dramatiq). Jobs need status, retry, cancellation, and visible logs/history — an observer
  running a multi-thousand-target sync must be able to see progress and failures, not just fire and
  forget.
- Add a **token-bucket rate limiter** (≤2 req/s) shared across all workers, applied to every
  CDS/VizieR/MAST call. Getting IP-banned from CDS is an existential risk to the whole project at
  scale.
- Move from per-target to **bulk nightly cross-match + local cache** wherever the source API
  supports it, rather than hitting CDS per candidate on demand.
- Add a **catalog abstraction layer** so a future Gaia DR4 migration is a config/mapping change,
  not an ingestion rewrite.
- Make the pipeline resumable and idempotent; record one `pipeline_run` row per execution
  (catalogs used + versions, targets processed, failures, duration) so every stored result is
  traceable to the exact run that produced it.

### D.3 API layer
- Version the API (`/api/v1` already exists — keep the discipline as it evolves) and publish a
  stable OpenAPI contract (FastAPI gives this almost for free via `/docs`; make sure schemas are
  accurate, not loosely typed `dict`).
- Server-side pagination, filtering, and sorting for `/candidates` (currently the frontend pulls
  `limit=100-150` and filters client-side).
- Add auth on write endpoints. `/pipeline/run` and the resolution-override endpoint are currently
  unauthenticated, and `main.py:24` sets `allow_origins=["*"]` — anyone who finds a deployed
  instance can trigger unbounded external API load or overwrite curator decisions. Minimum viable:
  API-key auth for `POST` endpoints; proper accounts can come later.
- Structured logging with real error taxonomy; remove any bare `except: pass`/`except Exception:
  print(...)` around scientifically meaningful code paths — errors in the science layer must be
  visible, not swallowed (this is the same principle as C.2's loud-failure requirement, applied
  everywhere).

### D.4 Packaging
- Add `backend/pyproject.toml` so the ingestion/feature/science modules are importable as a library:
  ```python
  from eefn import audit_candidate
  report = audit_candidate(toi="1017.01")
  ```
- Add a CLI (`eefn audit --toi 1017.01`, `eefn sync --sector 31`, `eefn export --format votable`).
- This is what converts EEFN from "a repo you clone" into "a tool you install" — high leverage for
  adoption relative to effort.

### D.5 Repo hygiene
- Move `project_dump/`, `scratch/`, and `backend/eefn.db` out of the public repo root — `scratch/`
  and `project_dump/` contain draft proposals and internal cleanup reports that shouldn't ship in a
  public release. Decide with the user whether to delete, `.gitignore`, or archive to a private
  location before the OSS release in Phase I — **do not delete anything without confirming**, some
  of it (like the 2MASS/Pan-STARRS fetch code, C.13/F below) is still needed as source material.
- Consolidate `validation/` similarly — keep the real audit scripts, retire redundant reports per
  the existing `project_dump/REPOSITORY_CLEANUP_PLAN.md`'s own classification (it's a reasonable
  plan, it just was never fully executed).

---

# PART E — PHASE 2: SCIENTIFIC CREDIBILITY

### E.1 Confront the label-leakage problem directly
Already correctly named in `LIMITATIONS.md` §1.1 — now actually run the mitigation:
- Evaluate on a **pre-Gaia-DR3-label subset** and report the performance delta vs. the full set.
- Build a **clean-label holdout** using only RV-mass-confirmed planets, independent of the
  TFOP/Gaia-informed disposition process.
- Publish the gap honestly, in `LIMITATIONS.md` and any public-facing docs. An 84%-accurate model
  with a *measured, disclosed* leakage gap is more credible and more citable than an unexamined
  95%.

### E.2 Calibration, not just accuracy
- Produce a reliability diagram (predicted probability vs. observed frequency) and report a Brier
  score. This is what a working scientist actually checks before trusting a stated probability.
- The DL net has a fixed `temperature=1.15` (`deep_learning_pipeline.py:126`) with no evidence it
  was fit on a validation set — do real temperature scaling as part of the retraining in C.2.

### E.3 Propagate uncertainty end to end
Catalogs already supply error columns (`st_tefferr1/2`, `st_raderr1/2`, `b_Rad`/`B_Rad`, etc.) and
ingestion fetches several already — stop discarding them. A derived radius should read
`5.46 ± 0.31 R⊕`, not a bare point estimate, everywhere it's shown.

### E.4 Benchmark against the field
Compare against published vetting tools on a common target set — **Robovetter**, **AstroNet**,
**ExoMiner**, and especially **TRICERATOPS** (the closest direct comparator — a statistical
validation tool astronomers already trust). Determine honestly whether EEFN adds signal on top of
these (its distinguishing angle is catalog-disagreement evidence, which they don't model) and say
so explicitly rather than implying novelty without checking.

### E.5 Get a real astronomer collaborator
One TFOP-affiliated collaborator using this for a real season is worth more than every item in this
plan combined for credibility. This is a relationship/outreach task for the user, not code — flag
it, don't try to automate it.

---

# PART F — PHASE 3: MODEL PIPELINE ARCHITECTURE + COMPLETING THE 7 CATALOGS

This phase must start **after** Phase 0 (a correct foundation) and should be designed from the
start for partial, heterogeneous catalog coverage — because with 7 catalogs, essentially no
candidate will ever have all 7.

### F.1 Tiered inference design

Do not build one big model requiring all inputs to be present. Instead, run the richest model whose
*required* inputs actually exist for a given candidate, and **record which tier produced the
result**:

| Tier | Requires | Component | Expected coverage |
|---|---|---|---|
| 0 | any data at all | Rule engine (`alert_engine.py`, post-C.3 unification) | ~100% — deterministic, already null-safe |
| 1 | NASA/TOI + Gaia (source + astroparams) | RF tabular model | ~95%+ — the dependable baseline |
| 2 | Tier 1 + real TESS light curve | Global+Local CNN branches | most 2-minute-cadence targets |
| 3 | Tier 2 + TPF centroid + 2MASS/Pan-STARRS/spectroscopy | Full 4-branch net | subset, but highest value when present |

Every API response and UI surface must show which tier ran and how many of the 7 catalogs actually
contributed (e.g. "Grade B, 4/7 catalogs available — no spectroscopy, no centroid"). A number
silently computed from zero-filled missing catalogs is worse than an honestly incomplete one.

### F.2 Missing-data masking, not default substitution

Building on C.6: every model input derived from an optional catalog needs a paired "present" bit,
not a physically-plausible default. For the DL metadata vector and the RF feature vector alike,
missingness must be representable and must not resolve to "looks clean." This directly fixes the
RUWE=1.0 and centroid=zeros bias identified in A.6.

### F.3 Modality dropout during training

Once centroid/spectroscopy/Pan-STARRS data genuinely exists (F.5-F.7 below), the DL model's
training loop must randomly zero-and-mask each optional branch some fraction of the time, so the
network learns robustness to the partial coverage it will see in production — not just trained
assuming every input is always present.

### F.4 Confidence shrinks with evidence, not just accuracy

A Tier-1-only candidate and a Tier-3 candidate might both return "82% consistent" — but the Tier-1
result should carry a visibly wider uncertainty band. Represent epistemic uncertainty from missing
catalogs explicitly (at minimum, widen the reported confidence interval as a function of tier/
catalog-coverage; a proper approach is an ensemble or MC-dropout spread, but even a coverage-based
heuristic is better than nothing, which is the current state).

### F.5 Recoverable catalogs: 2MASS + Pan-STARRS (fixes the 3/7 → 5/7 gap)

Port the working CDS X-Match calls from `scratch/download_real_sample_data.py:80-110` into
`ingest.py`'s cross-match loop, using the same `CDS_XMATCH_URL`/retry pattern already live for Gaia:
- 2MASS: `vizier:II/246/out` → `j_mag`, `h_mag`, `k_mag`.
- Pan-STARRS: `vizier:II/349/ps1` → `g_mag`, `r_mag`, `i_mag`, `z_mag`, `y_mag`.

Wire the results into `HostStar` (columns already exist) with full provenance
(`MeasurementHistory` rows per D.1) and respect the shared rate limiter from D.2. Extend the RF
feature vector and DL metadata vector to actually use these fields (currently the DL metadata
vector only consumes `j_mag`/`k_mag`, not `h_mag`, and doesn't use Pan-STARRS at all — expand it
deliberately, and retrain per C.2/F.3 whenever the input shape changes).

### F.6 New build: MAST FITS centroid analysis (highest scientific value)

Nothing real exists for this today — the "sample" in `download_real_sample_data.py` is
`np.random` noise. This is the single best discriminator against background eclipsing binaries
(the largest false-positive class), and `CentroidSpatialCNN` is already built and waiting for real
input.

- Add `astroquery` + `lightkurve` as real dependencies.
- Fetch Target Pixel Files (TPFs) via `astroquery.mast` for ingested targets.
- Compute intensity-weighted photocentre per cadence; measure in-transit vs. out-of-transit offset
  and its statistical significance (arcsec + sigma).
- This is genuinely heavy (GB-scale downloads, needs caching and async handling) — treat it as its
  own milestone with its own storage/caching design, not a quick add.
- Feed real centroid arrays into `CentroidSpatialCNN` at inference and — critically — into training
  (F.3) with correct masking for targets where no TPF was available.

### F.7 New build: real spectroscopy

Also currently fabricated (hardcoded dict, not an API call). Real work: query
APOGEE/GALAH/LAMOST via VizieR/TAP. These surveys have limited sky coverage — the pipeline must
degrade gracefully (Tier 3 requires it, Tiers 0-2 don't), and `completeness_score` (C.10) must
reflect real coverage, not assume it's always available.

**Sequencing within Phase F: F.1/F.2 (architecture) → F.5 (2MASS/Pan-STARRS, cheap+real) → F.6
(centroid, hardest but highest value) → F.7 (spectroscopy).** Do not start F.5-F.7 before F.1/F.2 —
adding catalogs to a pipeline that still zero-fills missing data multiplies the exact bias this
phase exists to fix.

---

# PART G — PHASE 4: INTEROPERABILITY (meet observers where they already work)

A standalone dashboard is an adoption blocker — observers live in ExoFOP and MAST, not a new
portal. Every item here removes a reason not to use EEFN.

| Integration | Why | Relative effort |
|---|---|---|
| VOTable / TAP export | How astronomers already consume data (TOPCAT, Aladin, `astroquery`) — near-free interop | Low |
| Python client / `astroquery`-style package | Drops EEFN into notebooks day one (ties to D.4) | Low |
| ExoFOP-TESS structured comments | Puts EEFN's flags on the page observers already read instead of asking them to leave it — needs coordination with ExoFOP maintainers | Medium |
| Webhooks / Slack | Most TFOP groups already run a triage channel; push into it rather than compete with it | Low |
| Consistent identifiers | Never make a user hand-translate TIC ↔ TOI ↔ Gaia source_id | Low |

Also: publish a citable dataset export with a Zenodo DOI per release (cheap, disproportionately
raises citation likelihood in any resulting paper).

---

# PART H — PHASE 5: FULL FRONTEND REDESIGN

The current frontend is a **showcase** — a WebGL nebula, a galactic 3D visualizer, glassmorphic
glowing cards, a decorative starfield behind every page. It is built to impress in the first 30
seconds. What's needed is an **instrument** — built to be trusted on the 200th night of use. That
distinction should drive every decision below.

**Do not treat this as a re-skin.** Read A.15 in full before starting — it documents the exact
current defects with file:line evidence. This phase removes them, it doesn't reskin them with
different colors.

## H.1 What "AI slop" means here — explicit anti-pattern checklist

Ban every item below. This list exists specifically so a fresh implementation doesn't drift back
into the same look under a new coat of paint:

- [x] Decorative background gradients, nebula blobs, dot-grids, or particle fields behind content —
      removed from the shared shell in a prior pass; home page's decorative hero gradient + orbiting
      circles removed this pass along with the rest of that marketing landing content.
- [x] `backdrop-filter: blur` "glassmorphic" panels used for resting content — `.glass-panel` was
      already made blur-free/token-based in a prior pass (verified: no `backdrop-filter` remains
      anywhere outside `Drawer.tsx`'s true modal overlay).
- [x] Glow/halo box-shadows on non-interactive elements — dead `glow-blue`/`glow-red`/`glow-green`
      class references (already no-ops, no matching CSS existed) removed from `candidates/[id]` and
      `predictions` for clarity; no live glow CSS remains anywhere.
- [x] Color as the *only* signal for status/severity/grade — `StatusIndicator`/`Badge`/`Callout`
      always pair color with an icon and/or text label; verified across the full screenshot sweep.
- [x] Grids of identical "icon + big number + small label" stat cards where a real data table would
      serve the task better — removed from the home page (was the worst offender); `showcase`/`demo`
      (explicitly out of scope, badged demo content per H.3.10) intentionally left as-is.
- [x] Hero sections, marketing copy, or centered vague taglines on any functional page — the home
      page's "Resolve uncertainty. Prioritise discovery." hero + CTA buttons removed entirely and
      replaced with the real triage queue; `showcase`/`demo` (badged demo content) intentionally
      exempted.
- [x] Motion applied uniformly for decoration — audited every `animate-*` usage across the app
      (2026-08-14). Found two real violations: a permanently-pulsing accent dot next to the static
      "PYTORCH MULTI-MODAL PIPELINE" / "B. PyTorch Deep ExoFusion Net" section labels in
      `candidates/[id]/page.tsx` (pulsed unconditionally, not tied to any loading/live state) —
      removed, now a flat dot. Everything else checked ties to real state: `animate-spin` on loading
      icons, `animate-pulse` on critical-severity values/disconnection text/an actively-recalculating
      signal, and a RUWE-conditional pulsing dot on the neighborhood-analysis star field (only renders
      when `ruwe > 1.4`, a real flagged-risk condition). `demo`/`showcase`'s `animate-slideUp`/
      `animate-ping` intentionally exempted (badged gallery content, presentation-mode motion).
- [x] Ad hoc hex/rgba colors, spacing, or radius values scattered through component files — all 9
      primary pages (`page.tsx`, `candidates/[id]`, `fusion`, `compare`, `graph`, `ai-analysis`,
      `admin`, `predictions`) migrated off hardcoded Tailwind slate/red/emerald/amber/sky/indigo/
      violet/rose classes onto the design-token system; `demo`/`showcase` intentionally exempted.
- [x] Icon styles mixed inconsistently across the app — audited 2026-08-14: every icon import across
      `app/`/`components/` is `lucide-react` (confirmed via import grep), but raw emoji (⚠️, ✅, ✓, ✗)
      were used as ad hoc icons alongside lucide components on the same pages/panels in
      `candidates/[id]/page.tsx` (5 occurrences) and `graph/page.tsx` (4 occurrences). Replaced all 9
      with the already-imported `AlertTriangle`/`CheckCircle2`/`XCircle` lucide icons. Also found and
      removed dead `glow-green`/`glow-yellow` class references (no matching CSS exists, confirmed via
      grep) left over in `graph/page.tsx` and `ai-analysis/page.tsx` from the same H.1 cleanup pass
      that removed them elsewhere; `demo`/`showcase` intentionally left as-is (exempted).
- [x] Nested cards inside cards inside cards — spot-checked the primary pages; the Evidence Card's
      derivation `<details>` blocks remain the one clear case of card-in-card structure and are
      intentional progressive disclosure, not accidental nesting. No unintentional multi-level nesting
      found elsewhere in this pass; not exhaustively verified against every one of `candidates/[id]`'s
      2,673 lines line-by-line.
- [x] A default, unmodified third-party component theme — the Radix primitives added this pass
      (`Badge`/`Callout`/`Tabs`/`Tooltip`/`Drawer`/`Table`) are styled entirely against this
      product's own tokens from the start, never a stock theme.

Before declaring Phase 5 done, go through this checklist against the running app page by page.

## H.2 Design system — build this first, before touching any page

> **Direction superseded 2026-08-13, by explicit user choice — read this note before the rest of
> H.2.** The instrument-panel-precision direction below was implemented once (bug fixes + token
> migration onto the existing dense, small-radius, no-shadow, IBM-Plex-Mono-heavy look) and shipped
> as "the redesign." The user rejected that result directly: *"the UI UX is still the same I wanted
> a more elegant and state of the art UI UX thats why I said full redesign."* Given an explicit
> `AskUserQuestion` choice between visual directions, they picked **"Modern SaaS dashboard"**
> (generous whitespace, soft shadows, rounded corners, lighter/approachable feel — Linear/Vercel/
> Notion/Stripe as references, not VizieR/TOPCAT/DS9/a trading terminal). That shipped as: indigo
> accent (`#4f46e5` light / `#818cf8` dark), a bigger radius scale (8/12/16/20px, not 4/6/8), soft
> `--shadow-sm/md/lg` elevation tokens applied to resting cards (not just overlays) via
> `design-tokens.css` + a global `[class*="border-border"][class*="rounded"]:not([class*="shadow-"])`
> CSS rule, and Inter unified as the dominant typeface with Space Grotesk headings removed. Red-night
> is the one exception: it keeps the flat, no-shadow, high-contrast treatment throughout regardless
> of this pivot, since night-vision preservation outweighs aesthetic consistency there. **The
> "instrument-panel precision, not consumer SaaS friendliness" framing immediately below is now
> historical context for why the first pass under-delivered — treat the modern-SaaS specifics above
> as the live direction, not the paragraphs that follow.** See
> [[feedback_eefn_redesign_and_devserver]] in memory for the full incident.

**Visual identity direction (superseded — see note above)**: instrument-panel precision, not
consumer SaaS friendliness. Mental reference points: professional astronomical/scientific tools
(VizieR, TOPCAT, DS9, the Gaia Archive), data-terminal density (Grafana, a trading terminal),
combined with the interaction polish of best-in-class modern product design (Linear, Vercel's
dashboard, Stripe's dashboard) — borrow their rigor and consistency, not their friendly-startup
visual voice.

**Typography** — the current font trio is a reasonable starting point, keep it but use it with
real discipline:
- `IBM Plex Mono` for all data values, numbers, identifiers (TOI/TIC IDs), timestamps — anything
  that benefits from fixed-width alignment.
- ~~A grotesk (keep `Space Grotesk` for headings, or evaluate a wider-weight-range alternative if
  needed) for headings/navigation only.~~ **Superseded**: Space Grotesk was dropped entirely
  2026-08-13; Inter now carries headings too, at weight 600, as part of the modern-SaaS unification.
- `Inter` (or similar) for body/UI text.
- Define one strict type scale and use it everywhere — no more ad hoc `clamp()` sizing per
  component. Example scale (adjust as needed, but pick one and stick to it):
  `11 / 12 / 13 / 14 / 16 / 20 / 28 / 40` px, with defined line-heights and letter-spacing per step.

**Color** — neutral-first, semantic-second, decorative-never:
- A full neutral gray ramp (10-12 steps) for structure, borders, backgrounds, text — this replaces
  the current single hardcoded `--surface`/`--line`/`--ink` set with a real scale.
- A small, fixed **semantic** palette used only for meaning:
  - Health grade A–F: a sequential, colorblind-safe scale (do not default to a raw red→green
    traffic light — validate with a colorblind simulation).
  - Alert severity: critical/high/medium/low, consistent across every surface that shows alerts.
  - Status: pass/watch/risk (already named in the codebase — keep the concept, fix the execution:
    always pair with an icon/label, never color alone).
- No decorative gradients anywhere. Backgrounds are flat, token-defined surfaces.
- Reference the `dataviz` skill's palette methodology when you get to actual chart colors (health
  distributions, calibration plots, etc.) — don't invent chart colors ad hoc.

**Spacing, radius, elevation** (radius/elevation bullets below superseded — see note above):
- 4px-base spacing scale, used everywhere via tokens — no arbitrary pixel values in component code.
- ~~Small radius scale (e.g. 4 / 6 / 8px) — retire the current large `rounded-2xl`/`rounded-3xl`-style
  softness in favor of a precise, technical feel.~~ **Superseded**: radius scale is now 8/12/16/20px
  (`--radius-sm/md/lg/xl` in `design-tokens.css`) as part of the modern-SaaS pivot.
- ~~Borders are the primary separator between regions. Shadows are reserved for true overlays
  (modals, dropdowns, drawers) — not resting cards.~~ **Superseded**: `--shadow-sm/md/lg` tokens now
  apply to resting cards (soft elevation), not just overlays, in light and dark themes. Red-night's
  shadow tokens remain `none`, so it still degrades to the original flat/border-only look there.

**Three themes — this is a functional requirement for the target users, not a nice-to-have:**
1. **Light/Day** — for daytime control-room/office use.
2. **Dark** — standard, refined version of the current concept minus every H.1 violation.
3. **Red/Night-vision** — near-black background, red-only text and accents, no blue light at all,
   for use at the telescope without destroying an observer's dark-adapted vision. This is a real,
   specific need for this exact user base — treat it as a first-class deliverable, not a stretch
   goal.
- Implement via CSS custom properties switched by a `data-theme` attribute (or the project's
  existing convention if one gets established) — never hardcode a color that only works in one
  theme.

**Implementation:**
- Create a single token source (`frontend/src/design/tokens.css` or a Tailwind theme extension —
  pick one approach and use it exclusively) covering color, type scale, spacing, radius.
- Reformat `globals.css`, `layout.tsx`, `ScientificUI.tsx`, `AppSidebar.tsx` out of their current
  single-line-per-file authoring style into normal, readable formatting as you touch them.
- Build a small primitive component library on **Radix UI primitives** (unstyled, accessible)
  styled against the new tokens: Table, Badge, Tag, Tabs, Drawer/Panel, Tooltip, Callout/Alert,
  Field/Input. One implementation of each, used everywhere — replace the current one-off styled
  JSX repeated per page.
- Consolidate `src/app/components/` and `src/components/` into a single location.
- Pick **one** 2D chart library for everything (recharts — already the more capable of the two
  currently installed) and remove `chart.js`/`react-chartjs-2`. Keep `three.js` **only** for the
  Explore/galactic view, and code-split/lazy-load it so it never loads on the triage or evidence
  pages.

## H.3 Information architecture — redesign around the observer's actual question

The organizing question for every screen: *"should I point a telescope at this tonight?"* — not
"how impressive can this look."

1. **Home = the triage queue**, not a landing page. Sortable/filterable/virtualized table:
   health grade, evidence-consistency score (post C.7 rename), disposition, follow-up priority,
   catalogs-used/completeness indicator, and — the highest-leverage addition — an
   **observability-tonight filter** (given an observer's site lat/long and date: altitude, airmass,
   moon separation, transit window). This is what turns EEFN into a daily tool instead of a
   one-time curiosity.
2. **The Evidence Card** (candidate detail) is the core artifact of the whole product. Design it
   with real care:
   - Every catalog's value for a field shown side by side, disagreements visually highlighted.
   - Provenance and query timestamp on every number (this is what `MeasurementHistory`, once
     populated per D.1, makes possible).
   - Uncertainties shown alongside every derived value (per E.3).
   - The health score broken down into its actual component deductions (the single unified formula
     from C.3), not just a bare letter grade.
   - Light curve viewer (global + local view) and, once real, a centroid-offset plot.
   - Alerts in plain language, each with its severity, explanation, likely cause, and recommended
     remediation (the `alert_engine.py` output already has this shape — design for it properly).
   - Which model tier (F.1) produced the score, and confidence that visibly reflects coverage (F.4).
   - An explicit **export to PDF / observing note** an astronomer can attach to a telescope-time
     proposal — this is a real, concrete "why I'd use this" feature.
3. **Compare** — 2–4 candidates side by side using the same field-level layout as the Evidence
   Card, not a separate visual language.
4. **Batch workflow** — upload a target list (CSV/TOI IDs), receive a ranked audit, export
   CSV/VOTable. This matches how observers actually work; single-target browsing is the exception,
   not the rule.
5. **Diff / "what changed" view** — "these N targets changed disposition or grade since your last
   sync." This is the strongest retention feature in the whole plan: it gives an observer a reason
   to open the tool every week even when nothing else changed.
6. **Explore** (the 3D galactic visualizer) — keep it, it's genuinely good for outreach and
   conference talks, but demote it to its own lazily-loaded route, not the front door.
7. **Predictions/model metrics page** — real, live-served evaluation artifacts (per C.8) plus the
   calibration/reliability diagram from E.2, not a hardcoded accuracy number.
8. **Admin** — real pipeline run history, per-source catalog health (last sync, failure rate,
   rate-limit status), not just a "run pipeline" button.
9. **An explicit "What this tool does and does not do" page**, linked prominently from the main
   nav, not buried in docs. This single page does more for trust than any visual polish.
10. **`demo/` and `showcase/`** — do not delete outright without asking the user (they may still
    want them for conference use), but remove them from primary navigation, move them under an
    `/explore` or `/gallery` path, and if kept, badge them unmistakably as demo content so they can
    never be confused with the live triage tool. Consider whether `ai-analysis` should be renamed
    away from its hype-adjacent name to something that honestly describes what it shows.

## H.4 Craft requirements (non-negotiable, check before calling this phase done)

- **Accessibility**: WCAG AA contrast minimum for all text, AAA preferred for primary data values;
  full keyboard navigation with real (not browser-default, not suppressed) focus states; every
  status/severity indicator has a non-color signal; respect `prefers-reduced-motion`.
- **Never render fabricated data indistinguishably from real data** (fixes A.14): on fetch failure,
  show an explicit, unmistakable error/unavailable state. If demo/sample data is ever shown, it
  must be clearly and permanently badged as such — never a silent substitute.
- **Performance**: virtualize any table that can exceed ~100 rows (the full TOI list is 7,000+);
  code-split the WebGL/three.js bundle away from the triage/evidence pages; lazy-load charts.
- **Responsive**: desktop-first (this is a professional tool used on real monitors) but must not
  break on a 13" laptop; mobile is at minimum a functional read-only glance, not full feature
  parity.
- **Testing**: Vitest + Testing Library for components/hooks; Playwright smoke tests for the core
  triage → evidence card → export flow.
- **Before declaring this phase complete**: actually start the dev server (`npm run dev`, or use
  the `run` skill if available) and look at every primary page in a real browser, in all three
  themes, checking against the H.1 checklist. A successful `npm run build` is necessary but not
  sufficient evidence of completion.

## H.5 Technical debt to clear while rebuilding

- Replace all 19 hardcoded `http://127.0.0.1:8000` occurrences with a single
  `frontend/src/lib/api.ts` client reading `process.env.NEXT_PUBLIC_API_URL`.
- Adopt **TanStack Query** for all data fetching (caching, retry, stale-state, loading/error
  states) instead of the current hand-rolled `useEffect` + `fetch` + local `useState` repeated in
  every page.
- Break every 400+ line page file into a data-fetching hook + composed presentational components.

---

# PART I — PHASE 6: RELEASE AND RECOGNITION

1. `LICENSE` + `README.md` (done in C.12) + `CONTRIBUTING.md` + `CODE_OF_CONDUCT.md`.
2. A documentation site (MkDocs or Docusaurus): quickstart, scientific methods with real formulas,
   API reference, and the "what EEFN does not do" page from H.3.9, reproduced in full here too.
3. **JOSS submission** (Journal of Open Source Software) — realistic scope for this project, gives
   a citable DOI, and is designed for exactly this kind of research software.
4. Zenodo DOI per release.
5. A real validation paper once Phase E is complete — the honest leakage analysis (E.1) is itself a
   publishable contribution, more interesting than "another vetting classifier."
6. Conference presence: TESS Science Conference, AAS, ADASS (ADASS specifically fits the software-
   architecture story).
7. One concrete, vivid published example: a real TOI where a catalog disagreement EEFN surfaced
   revealed a genuine problem. One true story travels further than any feature list.

---

# PART J — SEQUENCING

| Milestone | Contents | Notes |
|---|---|---|
| **M0 — Trustworthy** | Phase 0 (Part C) entirely | Strictly blocking. Nothing else starts before this is done. |
| **M1 — Deployable** | D.1–D.3, D.5, H.5, H.1–H.2 (design system) | Backend and frontend foundations can run in parallel once M0 is done. |
| **M2 — Installable** | D.4 (packaging/CLI), G (VOTable/TAP/Python client) | |
| **M3 — Defensible** | Phase E (leakage study, calibration, uncertainty, benchmark) | |
| **M4 — Complete data + model** | F.1–F.2 (architecture) → F.5 (2MASS/Pan-STARRS) → F.6 (centroid) → F.7 (spectroscopy) | Do not start before M0. F ordering is strict within itself. |
| **M5 — Instrument-grade frontend** | H.3 (information architecture), H.4 (craft) | Depends on H.2 (design system) from M1. |
| **M6 — Recognised** | Phase I | Ongoing after M0–M5. |

**Hard rule**: M4 (new catalogs) must not start before M0. Adding data sources to a pipeline that
currently fabricates its outputs (A.1, A.2) multiplies the problem rather than fixing it.

---

# PART K — RISK REGISTER

| Risk | Severity | Mitigation |
|---|---|---|
| An observer acts on a fabricated or stale number | Critical | Phase 0 in full; loud failure everywhere; provenance on every value; real upsert on re-ingest (C.10) |
| CDS/MAST rate-limit ban | High | Token bucket (D.2), bulk nightly sync, local cache |
| Gaia DR4 breaks ingestion later | High | Catalog abstraction layer (D.2) |
| Leakage discovered by an external reviewer before it's disclosed | High | E.1 — publish it yourself, first |
| Built for observers without ever involving one | High | E.5 — recruit a real collaborator early, not at the end |
| Frontend redesign drifts back into H.1-listed anti-patterns under time pressure | Medium | Check every page against the H.1 checklist explicitly before calling Phase 5 done |
| Scope sprawl across 7 catalogs + 2 models + a full redesign | Medium | Follow Part J's sequencing strictly; do not parallelize across phases that have a stated dependency |

---

# PART L — APPENDIX: CONSOLIDATED FILE-BY-FILE FIX LIST

Use this as a checklist while executing Phase 0/1/3; each row maps to a Part A finding and its Part
C/D/F fix.

| File | Issue | Finding | Fix |
|---|---|---|---|
| `backend/app/ml/predict.py` | RF never invoked; disposition read as the answer | A.1 | C.1 |
| `backend/app/ml/deep_learning_pipeline.py` | Untrained/random weights served silently | A.2 | C.2 |
| `backend/app/ml/train_deep_learning.py` | Trains old 8-feature/3-branch shape; synthetic-only light curves | A.2 | C.2, F.3 |
| `backend/app/pipeline/ingest.py` | Inline health score disagrees with `alert_engine.py` | A.3 | C.3 |
| `backend/services/alert_engine.py` | Inline health score disagrees with `ingest.py` | A.3 | C.3 |
| `backend/app/pipeline/ingest.py:215` | Density formula missing period, wrong units | A.4 | C.4 |
| `backend/app/ml/predict.py:93-99`, `deep_learning_pipeline.py:291-299`, `alert_engine.py:27-30` | Hard radius veto overrides model output | A.5 | C.5 |
| `backend/app/ml/deep_learning_pipeline.py:237-240`, `predict.py:87,109` | Missing data defaults read as clean | A.6 | C.6, F.2 |
| DB/schema/API/frontend, wherever `confirmation_probability` appears | Misleading name | A.7 | C.7 |
| `backend/app/api/endpoints.py:236-250` | Hardcoded fake model metrics | A.8 | C.8 |
| `backend/app/api/endpoints.py:222-233` | Background task uses closed DB session | A.9 | C.9, D.2 |
| `backend/app/pipeline/ingest.py` | Create-only guards, no upsert; hardcoded completeness | A.10 | C.10 |
| `backend/requirements.txt` | Missing `torch`; possibly-unused `neo4j` | A.11 | C.11 |
| repo root | No LICENSE/README; broken CI key | A.12 | C.12 |
| `backend/app/pipeline/ingest.py` | Only 3/7 catalogs live | A.13 | F.5, F.6, F.7 |
| `frontend/src/**` (19 call sites) | Hardcoded localhost API URL | A.14 | H.5 |
| `frontend/src/app/candidates/page.tsx:26-50` | Silent fabricated fallback data on fetch failure | A.14 | H.4 |
| `frontend/src/app/globals.css` and all pages | Decorative gradients/glass/glow; no tokens; one theme | A.15 | H.1, H.2 |

---

# PART M — DEFINITION OF DONE PER PHASE

Use these as literal checklists. Do not mark a phase complete in your task tracker until every box
is true and verified (tested/run, not assumed).

**Phase 0 (Part C)** — see the exit criteria listed at the end of Part C.

**Phase 1 (Part D)**
- [x] Postgres supported and used in at least one non-local environment; SQLite still works for dev.
- [x] Alembic migrations exist and are applied cleanly to a fresh DB.
- [x] `/pipeline/run` and override endpoints require auth.
- [x] `pip install -e backend` (or equivalent) installs EEFN as a library; a CLI command runs.
- [x] `MeasurementHistory` rows are actually written by ingestion, with source/version/timestamp.

**Phase 2 (Part E)**
- [x] A leakage-ablation result exists and is written into `LIMITATIONS.md`.
- [x] A reliability diagram / Brier score is generated and served/displayed somewhere real.
- [x] Derived values shown to users include propagated uncertainty.
- [x] A written comparison against at least TRICERATOPS exists.

**Phase 3 (Part F)**
- [x] Tiered inference is implemented; API/UI report which tier ran and catalog coverage.
      `tiers.py`/`model_tier` computed and returned by every relevant API response; the Evidence Card
      now shows a "Tier N · X/7 catalogs" badge (hover for the full available/missing list), and the
      Batch Workflow's ranked audit table shows tier + coverage per row.
- [ ] Missing-data masking replaces default-value substitution in both RF and DL feature pipelines.
      **DL only** — the 28-dim DL metadata vector has a presence bit per optional field (F.2); the
      RF path still uses median imputation (`SimpleImputer`), a different and still-disclosed
      (`LIMITATIONS.md` §1.3) form of default substitution, not presence-bit masking.
- [x] 2MASS + Pan-STARRS are live in `ingest.py` with provenance.
- [x] Real MAST/TPF centroid extraction exists and feeds `CentroidSpatialCNN` for at least a subset
      of targets. Verified live: TOI-104.01 (a real, 5.43-sigma measured offset) returns
      `dl_centroid_available: true` from `/transit_pipeline`.
- [x] Real spectroscopy ingestion exists (or is explicitly deferred with a documented reason).
      Real APOGEE-2 DR17 cross-match built and run (2/25 matched, honest given APOGEE's limited
      sky coverage) — see `LIMITATIONS.md` §1.8.

**Phase 4 (Part G)**
- [x] A TAP or VOTable export endpoint exists and validates in TOPCAT.
- [x] A documented Python client / package exists.

**Phase 5 (Part H)**
- [x] Every item in the H.1 anti-pattern checklist is verified false (i.e. absent) on every primary
      page. Home page's marketing hero/fabricated trend chart/decorative stat-card grid removed
      entirely (H.3.1 rebuild); all 8 remaining pages (`fusion`, `compare`, `graph`, `ai-analysis`,
      `admin`, `predictions`, `demo`, `showcase`) migrated off hardcoded Tailwind slate/emerald/
      rose/indigo/violet classes onto the design-token system; dead `glow-blue`/`glow-red` classes
      removed. Verified via a 39-screenshot sweep (13 pages x 3 themes).
- [x] Light, dark, and red/night themes all implemented and switchable, each passing a contrast
      check. A real WCAG contrast audit (`frontend/scripts/contrast_audit.py`, computed directly
      from the token hex values, not eyeballed) found 5 real failing pairs (light-theme amber grade-
      D/severity-high at 2.94:1, red-night muted text at 2.74-2.82:1, red-night severity-medium at
      2.74:1) — all 5 fixed by adjusting the token values; all 51 (17 pairs x 3 themes) now pass.
- [x] No hardcoded API URLs remain; app runs against a configurable backend. All 17 call sites go
      through `frontend/src/lib/api.ts` (`NEXT_PUBLIC_API_URL`, defaulting to `127.0.0.1:8000` for
      zero-config local dev).
- [x] Fetch failures produce an explicit error state, never silent fabricated data. This was a much
      deeper, systemic bug than first found: real fabricated fallbacks existed on `candidates/page.tsx`,
      `TelemetryBar.tsx`, `candidates/[id]/page.tsx` (an entire fake candidate profile + fake alerts +
      fake timeline), `compare/page.tsx` (two fake candidate profiles), `fusion/page.tsx` (fake catalog-
      consensus percentages plus a *formula that invented disagreement numbers per candidate*),
      `graph/page.tsx` (fake Neo4j graph, referencing a dependency removed in C.11), `predictions/page.tsx`
      (fake accuracy/ROC-AUC/F1 plus a fabricated "permutation test p=0.0000" claim), and `admin/page.tsx`
      (fake "CONNECTED" statuses and — worst — a fake "Pipeline execution completed" message shown
      regardless of whether the real backend call succeeded). All fixed with real data + honest error
      states; `admin/page.tsx` rebuilt against the real `/catalog/health` + `/pipeline/runs` endpoints
      (which themselves had a real A.8-class bug: `ingestion_success_rate`/`cross_match_success_rate`/
      `stale_record_rate` were hardcoded constants, now computed from real `query_failed`/`updated_at`
      data). Also found and removed a hardcoded, unverifiable literature-citation lookup table on the
      Evidence Card's alert panel, and fixed a real correctness bug where the frontend recomputed
      "unphysical radius" at a different threshold (20 R_Earth) than the real backend (22 R_Earth),
      which could show a false "DO NOT OBSERVE" verdict.
      **Addendum 2026-08-14**: this sweep did not catch everything. Found and fixed two more live
      instances of the same anti-pattern: (1) `candidates/[id]/page.tsx`'s `getTimelineEvents()` had
      an unconditional `id === "1017.01"` / `id === "1020.01"` branch returning a fully fabricated
      5-event narrative (invented years, invented Tmag/RUWE/Teff values, invented citations like
      "Stassun et al. 2018") that overrode the real `/timeline` fetch for those two specific
      candidates -- the two most-used demo/screenshot candidates in this whole project, so the fake
      provenance was the most-seen state of this panel. (2) `ai-analysis/page.tsx`'s three summary
      stat cards showed hardcoded fake numbers ("96"/"54"/"42") via `totalCount || "96"`-style
      fallbacks whenever the real fetch hadn't completed yet, instead of an honest loading state.
      Both fixed; verified via Playwright that the fake strings no longer appear. **Lesson**: an
      `[x]`-checked "no fabrication" sweep is a point-in-time claim, not a guarantee -- re-grep for
      hardcoded fallback literals (`|| "N"`, `? x : "N"`, per-ID special cases) before trusting this
      box on a file that wasn't specifically re-touched.
      **Addendum 2026-08-15**: a broader repo-wide grep for the same patterns (fallback literals,
      `Math.random`, hardcoded `id === "..."` branches) found three more instances, all in dead code:
      `CentroidShiftMap.tsx` (fabricated a fake "Photocenter Shift: 4.8σ (BEB Flag)" specifically for
      TOI-1017.01 from seeded `Math.sin`/`Math.cos` noise, not real centroid data),
      `TransitLightCurve.tsx` (drew a fake light curve from real depth/duration but filled it with
      synthetic scattered noise), and `NebulaCanvas.tsx` (the decorative starfield the H.1 pass
      removed the *usage* of but left the file behind). None were imported anywhere (confirmed via
      grep) -- leftover prototype components, not a live bug. Deleted with the user's explicit
      confirmation (this repo has no git, so deletion is permanent).
- [x] Home page is the triage queue with a working observability-tonight filter. `/` now renders the
      real server-paginated/virtualized/sortable triage queue directly (was previously only at
      `/candidates`, which now redirects to `/`). The observability filter uses real
      `astropy.coordinates`/`astropy.time` (`backend/app/science/observability.py`): altitude,
      airmass, moon separation/illumination, sky darkness, and — when a real transit epoch
      (`pl_tranmid`, newly added to the NASA TAP query) is on record — the actual transit window for
      that night. A candidate with no epoch reports that honestly rather than guessing one. Found and
      fixed a real ~30x performance problem during load-testing (196 candidates: ~32s looped vs ~1s
      vectorized) by batching the astropy computation across all targets in one call instead of one
      Python-level call per candidate — a genuine speedup, not just a higher timeout.
- [x] Evidence Card shows provenance + timestamp + uncertainty on every value, and the unified
      health-score breakdown. The backend now recomputes and returns the real
      `HealthResult.factors` breakdown (`app/science/health.py`) on every candidate-detail request;
      the frontend's own independent reimplementation of the health-score formula (a real,
      reintroduced A.3-class bug — it had invented "bonus" terms and a hardcoded "100% completeness"
      that didn't exist in the real formula) was deleted and replaced with the real data. Model tier +
      catalog coverage is now shown as a badge. A provenance table shows each measurement's real
      source, value, and `measured_at` timestamp (`MeasurementHistory.measured_at`, newly threaded
      through the API).
- [x] Batch upload/export and the diff/"what changed" view both work end to end. `/batch`: paste/
      upload a TOI list, get a real ranked audit (`POST /api/v1/batch/audit`, reuses the same
      `build_candidate_profile` real data path as single-candidate lookups) with CSV and real VOTable
      export. `/changes`: a real, timestamped `disposition_change_events` ledger written by
      `ingest.py`'s upsert path only when a re-ingested candidate's disposition/health_grade
      genuinely differs from what was already stored — verified via a real PC-to-FP flip in the
      existing upsert test suite. An empty result on `/changes` today is the honest, correct
      state (no real transitions recorded yet since this feature was added), not a bug.
- [x] Dev server actually run and visually checked, all three themes, by a human or the `run` skill
      — not just a passing build. `claude-in-chrome` browser automation was unavailable this session
      (extension not connected); verification was via `npm run build`, a live backend + frontend dev
      server, curl/SSR content checks, a real WCAG contrast audit, and a 39-screenshot Playwright
      sweep (13 pages x 3 themes) that was actually read and inspected, catching two real remaining
      issues (a stale hardcoded architecture diagram on the DL demo page, a fabricated resolution-
      confidence table on the graph page) that were then honestly disclosed in-app rather than fixed
      with more fabrication. This is real functional + visual verification, but not the same as a
      human or live-browser click-through — still disclosed as the one gap in this checkbox.

**Phase 6 (Part I)**
- [x] LICENSE, README, CONTRIBUTING, CODE_OF_CONDUCT all present.
- [ ] Docs site builds and is deployed somewhere.
- [ ] A JOSS submission draft exists (submission itself is the user's call, not autonomous).

---

# CLOSING — the one-line test

Before adding, building, or polishing anything not explicitly in this plan, ask: **does this make a
working astronomer more likely to trust EEFN and actually use it on a Tuesday night?** A nebula
animation does not. A correct uncertainty value, a provenance timestamp, an observability filter,
a `pip install`, and a page that never lies about where its numbers came from, do.
