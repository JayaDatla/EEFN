# Contributing to EEFN

EEFN is scientific infrastructure, not a demo. The bar for a contribution is the same
bar the rest of the project holds itself to (see `UPGRADE_PLAN.md`'s "never fabricate"
rule): if real data isn't available, show an explicit "unavailable" state — never a
plausible-looking substitute.

## Before you start

1. Read `README.md`, `LIMITATIONS.md`, and `DATA_FLOW.md` — they describe what EEFN
   actually does, what it doesn't, and where every number in the system comes from.
2. If you're picking up planned work, `UPGRADE_PLAN.md` is the authoritative execution
   spec — check it before starting so you don't duplicate or contradict in-flight work.
3. For anything not covered by the plan, open an issue describing the change before
   sending a large PR — this is especially true for anything touching the science layer
   (`backend/app/science/`, `backend/app/ml/`) or the health-score formula.

## Development setup

- **Backend**: `backend/README`-equivalent is the root `README.md` quickstart. Use
  `requirements.txt` (+ `requirements-dev.txt` for tests), run `alembic upgrade head`
  against a fresh database, then `uvicorn main:app --reload`.
- **Frontend**: `cd frontend && npm install && npm run dev`.
- **Tests**: `cd backend && python -m pytest tests/ -q`. Every backend change should
  come with a test — especially a regression test for any bug class described in
  `UPGRADE_PLAN.md` Part A, several of which exist specifically to prevent silent
  regressions (e.g. "inference output must not change when `disposition` is mutated").
- **Frontend verification**: a successful `npm run build` is necessary but not
  sufficient. Actually run `npm run dev` and look at the page you changed, in more than
  one theme if you touched anything visual.

## What we will not merge

- Any hardcoded or fabricated value presented as if it were computed from real data
  (see `UPGRADE_PLAN.md` Part A for what this looked like historically and why it's
  banned).
- A missing/optional catalog value silently defaulted to a "looks clean" placeholder
  (RUWE defaulting to 1.0, a missing centroid defaulting to all-zeros, etc.) instead of
  carrying an explicit presence flag.
- UI that reintroduces anything on the `UPGRADE_PLAN.md` H.1 anti-pattern checklist
  (decorative gradients, glassmorphism on resting content, color as the only status
  signal, etc.).
- A new external catalog call with no rate limiting, or added to the hot request path
  instead of the shared token-bucket limiter (`app/pipeline/rate_limiter.py`).

## Code style

- Backend: standard PEP 8, type hints where they add clarity, comments only where the
  *why* isn't obvious from the code (see the existing codebase for the house style —
  most comments reference the specific `UPGRADE_PLAN.md` section a piece of code
  implements).
- Frontend: normal (non-minified) formatting, Tailwind classes routed through the
  design tokens in `frontend/src/app/design-tokens.css` rather than hardcoded colors.

## Pull requests

- Keep PRs scoped to one change. A bug fix doesn't need accompanying refactors.
- Include what you tested and how in the PR description — "ran the test suite" plus,
  for anything scientific, what real inputs you checked the output against.
- Be honest in the PR description about what's still incomplete, the same way
  `LIMITATIONS.md` is honest about the project as a whole.
