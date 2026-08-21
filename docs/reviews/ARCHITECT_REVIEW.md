# Board D: Principal Software Architect Review

**Review Panel Roles**:
*   Staff Software Engineer
*   Principal Distributed Systems Architect
*   Site Reliability Engineer (SRE)

---

## 1. Architectural Overview
EEFN is designed as a classic decoupled web application: a FastAPI python backend connected to a SQLite relational database, with a Next.js frontend communicating via REST endpoints. While this architecture is clean and highly suitable for single-user research work, it has several critical engineering risks that prevent immediate production deployment.

---

## 2. Technical Debt and System Risks

### 1. SQLite Concurrency Blocker
*   **Risk Level**: **HIGH**
*   **Description**: The application uses SQLite as its relational datastore. While SQLite is excellent for read-heavy operations, it does not support high-concurrency writes.
*   **Impact**: When multiple users trigger manual overrides or the background ingestion pipeline runs, SQLite's database-level lock will cause transaction timeouts (`sqlite3.OperationalError: database is locked`) and API crashes.
*   **Fix**: Migrate the production database configuration to a robust PostgreSQL cluster.

### 2. Lack of Asynchronous Task Queuing
*   **Risk Level**: **MEDIUM**
*   **Description**: The `/pipeline/run` endpoint utilizes FastAPI's built-in `BackgroundTasks` to trigger long-running astronomical queries and ML predictions.
*   **Impact**: In-process background tasks run on the same CPU cores as the web server. If a user runs a large ingestion pipeline (e.g. 500 objects), the web API will lag, drop requests, or crash under out-of-memory (OOM) limits.
*   **Fix**: Implement a dedicated task queue (e.g., Celery or Redis Queue) to execute pipeline ingestions out-of-process on worker nodes.

### 3. Rate-Limiting Vulnerability with CDS/MAST
*   **Risk Level**: **HIGH**
*   **Description**: The pipeline directly queries CDS Aladin, VizieR, and MAST APIs in synchronous loops.
*   **Impact**: These public astronomy services enforce strict rate limits. Direct, unthrottled requests from EEFN will result in IP blocks, 429 Too Many Requests errors, or silent failures (which default to missing values in the DB).
*   **Fix**: Implement a rate-limiting proxy layer and request queue (with exponential backoff) for all third-party astronomical API clients.

### 4. Absence of Security / Authentication
*   **Risk Level**: **HIGH**
*   **Description**: The manual override endpoint `/candidates/{toi_id}/resolution/override` allows writing directly to the database without authentication or request signing.
*   **Impact**: Anyone on the network can spoof requests and corrupt the entity mappings in the database.
*   **Fix**: Implement JWT-based user authentication and strict Role-Based Access Control (RBAC).

---
*Architectural Verdict: REJECT FOR PRODUCTION (Requires database migration and task queue refactoring)*
