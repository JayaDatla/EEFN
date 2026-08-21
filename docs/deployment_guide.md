# EEFN Platform Deployment Guide

This document provides instructions for deploying the **Exoplanet Evidence Fusion Network (EEFN)** Evidence Quality Intelligence Platform in a production-grade multi-container environment.

---

## 1. Production Docker Orchestration

The platform is orchestrated via `docker-compose` and is designed to run four primary services:
1.  **PostgreSQL (`eefn_postgres`):** Relational database storage.
2.  **Neo4j Community Edition (`eefn_neo4j`):** Graph entity resolution storage.
3.  **FastAPI Backend (`eefn_backend`):** Main REST API engine.
4.  **Next.js Frontend (`eefn_frontend`):** Mission operations curation dashboard.

### `docker-compose.yml` Configuration
To start the services locally or on a production node:
```bash
docker-compose up -d --build
```

---

## 2. Environment Variables Configuration
Ensure the following variables are defined in your production `.env` file:
```text
# Databases
DATABASE_URL=postgresql://eefn_user:secure_password@postgres:5432/eefn_db
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=secure_neo4j_password

# Server Settings
ENV=production
API_CORS_ORIGINS=["https://eefn.yourdomain.org"]
NEXT_PUBLIC_API_URL=https://api.eefn.yourdomain.org
```

---

## 3. High-Throughput & Rate Limit Mitigations
When deploying the ingestion worker in production:
*   **CDS X-Match API Retries:** The ingestion script is equipped with a `post_with_retry` function that catches CDS rate-limit warnings ("Too many jobs are being processed") and sleeps for 6.0 seconds between retries.
*   **Relational Fallback:** If the external Gaia VizieR or NASA TAP servers are completely offline or rate-limiting persists, the pipeline degrades gracefully by utilizing the TESS catalog's native stellar properties and defaulting Gaia-specific columns, avoiding pipeline failures.
