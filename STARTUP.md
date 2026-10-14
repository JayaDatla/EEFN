# Running EEFN locally

Four things need to be running for the site to work: Redis, the FastAPI backend,
the Arq background worker, and the Next.js frontend. This is the actual local
dev setup (SQLite, standalone Redis container) — not `docker-compose.yml`,
which describes a separate, Postgres-based containerized deployment that
isn't what your local data/predictions are running on.

## One-time setup

```bash
# Backend deps (no virtualenv in use -- installs into the system Python)
cd backend
pip install -r requirements.txt

# Frontend deps
cd ../frontend
npm install
```

No `.env` file is needed for local dev — the backend defaults `REDIS_URL` to
`redis://localhost:6379/0` and the frontend defaults its API base to
`http://127.0.0.1:8000` when `NEXT_PUBLIC_API_URL` isn't set.

## Every time: start in this order

**1. Redis** (only if not already running)
```bash
docker start eefn_redis
# or, if that container doesn't exist yet:
docker run -d --name eefn_redis -p 6379:6379 redis:7-alpine
```

**2. Backend** (from `backend/`)
```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**3. Arq worker** (from `backend/`, separate terminal)
```bash
python -m arq app.worker.WorkerSettings
```
This runs the background pipeline sync jobs. The site works without it, but
"Force Pipeline Sync" on the Admin page and anything you queue will just sit
at `QUEUED` forever.

**4. Frontend** (from `frontend/`, separate terminal)
```bash
npm run dev
```

Then open **http://localhost:3000**.

## Verify everything's actually up

```bash
curl http://localhost:8000/                          # backend -> {"status":"online",...}
curl http://localhost:8000/api/v1/candidates?limit=1  # DB is readable
curl http://localhost:3000/                           # frontend -> 200
docker ps --filter name=eefn_redis                    # redis -> "healthy"
```

## If a page won't load

It's almost always the backend or the worker having silently died in the
background, not a real content bug — check before assuming otherwise:

```bash
netstat -ano | grep -E ":3000|:8000|:6379" | grep LISTENING
```

If port 8000 or the worker process is missing, just re-run steps 2/3 above.
The backend takes a few seconds to become ready (it loads the DL model
checkpoint on startup) — a `curl` right after launching can briefly return
nothing before it's up.
