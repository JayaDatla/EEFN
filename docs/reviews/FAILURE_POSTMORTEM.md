# Board F: Three-Years-Later Failure Analysis

**Date of Postmortem**: June 11, 2029  
**Subject**: Exoplanet Evidence Fusion Network (EEFN)  
**Status**: **DEPRECATED / INACTIVE** (Failed to achieve community adoption)

---

## 1. Executive Summary of Failure
Released in 2026, EEFN aimed to transform exoplanet catalog curation and coordinate cross-matching. By 2029, the project is abandoned. No major astronomical database integrated the software, ground-based observatories did not adopt the pipeline, and the GitHub repository has been dormant for 18 months. This document analyzes the structural and scientific failures that led to this outcome.

---

## 2. Structural Root Causes of Failure

### 1. The Standalone Portal Trap (User Adoption Failure)
*   **Assumption**: The developers assumed that observers and astronomers would log into the EEFN Next.js web portal to check targets and alerts prior to telescope observing runs.
*   **Reality**: Observers are overwhelmed by the number of standalone dashboards. Astronomers continued to rely on **ExoFOP** and the **NASA Exoplanet Archive** as their single sources of truth. Since EEFN did not directly integrate its alerts into ExoFOP, it was ignored by the telescope community.

### 2. The API Rate-Limit Block (Technical Limitation)
*   **Assumption**: The automated ingestion pipeline was built to pull data dynamically from VizieR, MAST, and CDS.
*   **Reality**: As a few research groups began using the tool, the concurrent API requests triggered IP blocks from the CDS Strasbourg and MAST servers. The pipeline crashed with `429 Too Many Requests` and `503 Service Unavailable`. Because the developers did not build a database caching proxy or asynchronous queues, the tool became unusable.

### 3. Catalog Obsolescence (Maintenance Failure)
*   **Assumption**: The database model assumed a static Gaia DR3 structure.
*   **Reality**: The release of **Gaia DR4** in late 2027 changed the astrophysical parameter tables and schemas. Because EEFN was written with hardcoded VizieR query strings and SQLite schema bindings, the entire ingestion pipeline broke. With no funding to pay a research software engineer to rewrite the catalog mapping layers, the project was abandoned.

### 4. Overlapped by Native Gaia Integration in ExoFOP (Competition)
*   **Assumption**: EEFN believed it had a unique value proposition in combining TESS and Gaia parameters.
*   **Reality**: In 2027, ExoFOP natively integrated Gaia DR3 parallaxes, RUWE, and radii directly into their main portal tables. Observers no longer needed a separate "fusion network" tool to see if a star had a high RUWE or unphysical radius.

---

## 3. Core Lessons Learned
*   **Integration over Standalone**: In scientific computing, success is achieved by integrating into existing archives (like IPAC/MAST), not by hosting new frontend dashboards.
*   **Database Schema Flexibility**: hardcoding catalog formats (like GAIA DR3 columns) leads to instant technical obsolescence when new data releases occur.
