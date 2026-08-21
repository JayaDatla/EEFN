# EEFN Demo Readiness Plan

**Created**: 2026-08-21
**Purpose**: Get EEFN into a state that can be demonstrated to a project guide with confidence.
**Scope**: This is a *stabilisation* plan, not a feature plan. It supersedes nothing in
`UPGRADE_PLAN.md` — that remains the long-term spec. This document covers only what stands
between the current state and a demo that works and tells the truth.

---

## 0. Current state, honestly stated

Verified live on 2026-08-21, not assumed:

| Component | State | Notes |
| :--- | :--- | :--- |
| Frontend (`:3000`) | **UP** | Next.js dev server running |
| Redis (`:6379`) | **UP** | Docker container `eefn_redis` |
| Backend (`:8000`) | **DOWN** | uvicorn process was stopped |
| Arq worker | **DOWN** | pipeline runs will queue forever without it |
| **DL model** | **DEGRADED** | `model_status="untrained_fallback"`, `degraded=True` |
| Database | **OK** | 546 real candidates, fully re-synced |
| Backend tests | **OK** | 102/102 passing |
| Git | **ABSENT** | no repo in this working directory — no undo safety net |

### Why the DL model is broken (read this first)

This is self-inflicted and needs to be understood before it is fixed. During the
"train on real data" work, `DL_ARCHITECTURE_VERSION` was bumped from
`...3ch-centroid.3` to `...3ch-centroid.3class-real.1` and the model was changed from
4 output classes to 3 — **but the retraining never completed**, because the real-data
fetch died partway through on a transient DNS failure
(`Failed to resolve exoplanetarchive.ipac.caltech.edu`).

The on-disk checkpoint `model_weights.pth` is still the old 4-class synthetic one. The
version-mismatch guard (working exactly as designed, per `UPGRADE_PLAN.md` C.2)
correctly refuses to load it and reports `degraded`. So the system is *honest* about
being broken, but it is broken.

**Nothing is silently lying. But the DL classification is currently meaningless.**

---

## Phase 0 — Unblock the demo (must do)

### 0.1 Decide the model strategy — DECISION REQUIRED

Two viable paths. This is the single highest-stakes decision in this plan.

**Path A — Finish the real-data training** *(what was asked for; higher value, higher risk)*
- Re-run `fetch_real_kepler_dataset.py` (resumable — 13 stars already cached, it skips them).
- Estimated wall-clock: ~2–4 hours for 180 stars, network-bound, unattended.
- Then run `train_deep_learning.py`, verify held-out accuracy, redeploy.
- **Risk**: if the network drops again close to demo time, the model stays degraded.
- **Payoff**: the "trained on synthetic data" disclaimer disappears for real. This is a
  genuinely defensible scientific claim to make to a guide.

**Path B — Roll back to the working synthetic checkpoint** *(safe, fast, honest-but-limited)*
- Revert `DL_ARCHITECTURE_VERSION` to `exofusion-net-v2.4branch.28feat.3ch-centroid.3`.
- Revert `num_classes` to 4 and restore the 4 class names.
- Model loads immediately, `degraded=False`, demo works in ~5 minutes.
- **Cost**: the model is back to synthetic-trained, and `LIMITATIONS.md` §1.7 stands.

**Recommendation**: attempt **Path A now**, with **Path B as a hard fallback** if the
dataset is not built and verified at least 24h before the demo. The two are not mutually
exclusive — Path B is a 5-minute revert that can be executed at any point.

- [ ] Decision made and recorded here: __________

### 0.2 Restore running services

```bash
# Backend
cd backend && python -m uvicorn main:app --reload --port 8000

# Redis (if not already up)
docker compose up -d redis

# Arq worker — REQUIRED for /pipeline/run to actually execute
cd backend && python -m arq app.worker.WorkerSettings

# Frontend
cd frontend && npm run dev
```

- [ ] All four services confirmed up (`curl :8000/docs`, `curl :3000`)
- [ ] `GET /api/v1/catalog/health` returns real counts

**Gotcha, learned the hard way this session**: the Arq worker does **not** hot-reload.
After any change to `ingest.py` or anything it imports, the worker must be restarted or it
will silently keep running the old code. Same applies to `services/` changes and uvicorn —
`--reload` did not reliably pick those up either; a full restart was needed twice.

### 0.3 Write a demo runbook

Before demoing, write down the exact click-path to be shown, and walk it end-to-end once.
Do not improvise in front of the guide — several pages have known rough edges (§2).

- [ ] Runbook written (suggested path in §4)
- [ ] Full click-path rehearsed with all services running

---

## Phase 1 — Complete the real-data training (Path A)

### 1.1 Make the fetch resilient

The fetch is currently one long unprotected run — a single DNS blip killed a ~40-minute job
and saved nothing. It caches per-star light curves (good), but loses all processed work.

- [ ] Wrap the NASA TAP query in a retry-with-backoff (the CDS/NASA calls in `ingest.py`
      already use `post_with_retry` — reuse that pattern rather than inventing a second one)
- [ ] Save the dataset incrementally (per class, or every N stars) so a crash keeps progress
- [ ] Add `--resume` so a re-run skips already-processed stars

### 1.2 Run the fetch at scale

```bash
cd backend
python validation/scripts/fetch_real_kepler_dataset.py --per-class 60
```

- [ ] Dataset built at `validation/data/real_kepler_training_set.npz`
- [ ] `app/ml/real_kepler_dataset_report.json` reviewed — check per-class usable counts are
      roughly balanced. If one class is starved, fetch more for that class specifically.

### 1.3 Train and verify

```bash
cd backend && python -m app.ml.train_deep_learning
```

- [ ] Training completes; `dl_training_report.json` written
- [ ] **Held-out test accuracy is the number that matters** — the old script only ever
      reported *training* accuracy (99.58%), which for a model trained and evaluated on its
      own synthetic generator was meaningless. The new script holds out real stars at the
      *star* level. Report that number, not the training number.
- [ ] Checkpoint verified to load: `model_status == "trained"`, `degraded == False`
- [ ] `/api/v1/candidates/{toi}/transit_pipeline` returns a real 3-class classification

### 1.4 Sanity-check the result before believing it

A high number here is not automatically good news.

- [ ] If held-out accuracy is suspiciously high (>95%), investigate before reporting it —
      with only ~180 stars and 4x augmentation, leakage or class imbalance is more likely
      than genuine skill.
- [ ] If accuracy is poor (<60%), say so. That is a legitimate finding for a first real
      training run on a small sample, and far better than a fabricated number.
- [ ] Record the honest result in `LIMITATIONS.md` either way.

---

## Phase 2 — Backend correctness

### 2.1 Known-fixed this session (verify still true, do not redo)

These were found, fixed, and live-verified. Re-confirm after any restart:

- [x] `ingest.py` no longer writes `0.0` for missing catalog comparisons (was making
      "no Gaia match" indistinguishable from "perfect agreement")
- [x] `AgreementMetrics` disagreement columns nullable + migration applied
- [x] NASA TAP query ordering fixed (`ORDER BY toi+0 ASC`) — lexical sort was silently
      skipping most TOIs in the 100–999 range on any limited sync
- [x] `audit_timeline.py` rewritten — was fabricating years, stellar values, match
      distances, and a fixed `resolution_confidence: 0.99`; also crashed on null stellar data
- [x] `/compare` derived-radius field reference corrected
- [x] `preprocess_lightcurve` bin-folding fix (pointwise interpolation was corrupting real
      multi-cycle light curves — verified against real confirmed planet KIC 10797460)

### 2.2 Open backend items

- [ ] **Stale `QUEUED` pipeline runs** from before the worker existed still show in `/admin`.
      Either purge them or render them as "abandoned (no worker)" rather than implying
      they are pending.
- [ ] **`/admin` gives no signal when no worker is running.** An operator sees runs sit at
      QUEUED with no explanation. Add a worker-heartbeat indicator or an explicit warning.
- [ ] **`/graph` resolution-confidence panel is still disclosed-fake** (hardcoded lookup for
      a few TOIs). It carries a visible Callout saying so, which is honest, but for a demo
      consider hiding the panel entirely rather than showing something labelled "not real".
- [ ] **RF still median-imputes** instead of using presence bits (`LIMITATIONS.md` §1.3).
      Known, disclosed, not demo-blocking.

---

## Phase 3 — Frontend declutter

The frontend is doing too much at once. Concrete measurements:

| Page | Lines | Assessment |
| :--- | ---: | :--- |
| `candidates/[id]` (Evidence Card) | **2,692** | Far too much in one file; 6+ tabs |
| `graph` | 787 | Contains a disclosed-fake panel |
| `ai-analysis` | 667 | **Stale hardcoded stats — see 3.2** |
| `showcase` | 615 | Duplicate of `demo` |
| Nav items | **12** | Too many top-level destinations for a demo |

### 3.1 Reduce navigation surface

12 primary destinations is more than a guide can follow. Group into ~4 clusters:

- **Triage** — Triage Queue (the home page, the actual product)
- **Evidence** — Evidence Explorer, Catalog Cross Reference, Evidence Graph
- **Models** — ML Predictions, DL Model Demo
- **Operations** — Pipeline Admin, Batch, What Changed
- **(footer/secondary)** — What This Tool Does, Gallery/demo content

- [ ] Sidebar regrouped with section headers, secondary items de-emphasised
- [ ] Confirm the demo path touches ≤5 pages

### 3.2 Fix the stale hardcoded model stats (`ai-analysis`) — HIGH PRIORITY

`ai-analysis/page.tsx` hardcodes numbers from an **old synthetic 4-class training run**:

| Line | Value | Problem |
| :--- | :--- | :--- |
| 299 | `1,182` total samples | From the old synthetic run |
| 309 | `99.58%` final accuracy | Synthetic *training* accuracy — misleading |
| 314 | `0.0114` final loss | Stale |
| 362/374/386 | class sample counts | **4-class distribution; model is now 3-class** |
| 263 | `3,863,844` weights | Will change with `num_classes` |

This is exactly the failure mode the project exists to eliminate — a confident number on
screen with nothing real behind it. It is also the page most likely to be shown to a guide.

- [ ] Serve these from `app/ml/dl_training_report.json` via a real endpoint (same honesty
      contract as `/predictions/metrics`: **503 if the artifact is missing**, never a
      hardcoded fallback)
- [ ] Frontend renders whatever the endpoint returns, or an explicit empty state
- [ ] Remove the 4th class from the architecture diagram and class-distribution panel
- [ ] Surface **held-out** accuracy, clearly labelled as such — not training accuracy

### 3.3 Resolve the demo/showcase duplication

`demo/page.tsx` now re-exports `showcase/page.tsx` (dedup already done), but **neither
page's content matches its nav label** — "API Explorer" and "Research Analytics" both render
the same generic outreach deck.

- [ ] Either build real content for each label, **or** collapse to a single "Project
      Overview" gallery entry and drop the other. For a demo, collapsing is the honest move.

### 3.4 Evidence Card (2,692 lines)

Not demo-blocking, but the single biggest maintenance liability in the frontend.

- [ ] Extract each tab into its own component file (telemetry / visualizer / pipeline
      diagnostics / demo mode) — mechanical, low-risk, large readability win
- [ ] Confirm the `model_status` / `degraded` badge is visible on this page **before**
      demoing — it is the page most likely to show a DL classification

---

## Phase 4 — Suggested demo path

A short, rehearsed path that shows real strength and avoids known rough edges:

1. **Triage Queue** (`/`) — 546 real candidates, real priority ranking, real
   observability-tonight filter. This is the strongest page. Lead with it.
2. **Evidence Card** — pick a candidate with real Gaia data (**not** TOI-104.01, which has
   no Gaia match and shows N/A across the board). Show the derived-radius audit and the real
   health-score breakdown.
3. **Evidence Explorer** (`/fusion`) — real catalog disagreement, and honestly shows
   "NO GAIA MATCH" where data is genuinely absent. This is a *strength* — point it out.
4. **ML Predictions** — real RF metrics from a real held-out split (85.02% / ROC-AUC 0.9237
   / Brier 0.1127), plus the honest calibration caveat.
5. **What This Tool Does** (`/about`) — closes on the limitations. A guide will respect
   this far more than an overclaim.

**Talking points that are genuinely defensible:**
- Real cross-match of 5 live catalogs, with full per-measurement provenance
- Catalog-disagreement features that a single-catalog pipeline structurally cannot compute
- A real 5.43σ centroid detection on TOI-104.01 from actual TESS pixel data
- Two real label-leakage ablations that were run and reported *as-is*, including a result
  that did not support the original hypothesis
- Every model output carries `model_status` / `degraded` — the system refuses to pretend

**Do not claim**: that the DL model is validated (it is not, under either path), or any
number from `ai-analysis` until §3.2 is done.

---

## Phase 5 — Safety

### 5.1 Initialise git — do this first, before any Phase 1–3 edits

There is still no version control in this working directory. A `Write` to the wrong file
destroyed `app/db/models.py` earlier in this project's history and it had to be manually
reconstructed from Alembic migrations. That risk is live every time this plan is executed.

```bash
cd /d/Gemini_Projects/EXO
git init
git add -A          # .gitignore already excludes project_dump/, scratch/, *.db, node_modules/
git commit -m "Checkpoint before demo-readiness work"
```

- [ ] Repo initialised and an initial commit made
- [ ] Confirm `backend/eefn.db` and `node_modules/` are **not** staged

### 5.2 Back up the trained artifacts

`model_weights.pth`, `model_artifacts.pkl`, and `eefn.db` are gitignored and irreplaceable
without a full retrain / re-sync.

- [ ] Copy `backend/app/ml/*.pth`, `*.pkl`, and `backend/eefn.db` somewhere outside the repo

---

## Execution order

```
5.1  git init                      ← do this FIRST, before touching anything
0.2  restore services              ← 5 min, unblocks everything else
0.1  model decision                ← decide now; Path B is a 5-min escape hatch
1.x  real-data training            ← start early, it is unattended wall-clock
3.2  fix stale ai-analysis stats   ← highest-value frontend fix
3.1  reduce nav surface
3.3  resolve demo/showcase
0.3  write + rehearse runbook      ← do this LAST, against the final state
2.2  backend polish                ← as time allows
3.4  Evidence Card refactor        ← post-demo
```

**If time is short, the minimum viable demo is**: 5.1 → 0.2 → 0.1 (Path B) → 3.2 → 0.3.
That is achievable in well under a day and yields a system that works and does not lie.
