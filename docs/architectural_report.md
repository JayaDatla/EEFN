# ExoFusion-Net (EEFN) Technical Audit & Architectural Report

---

## 1. Executive Summary

### What is this project?
The Exoplanet Evidence Fusion Network (EEFN) is a high-integrity, data-dense scientific pipeline and vetting workstation designed to resolve catalog parameter discrepancies and audit planet candidate classifications. By dynamically cross-matching candidate tables with Gaia DR3 high-precision parallax data, spectral databases, and photometric catalogs, EEFN resolves astronomical dataset discrepancies.

### Primary Purpose
To automate exoplanet validation, calculate astrophysical invariants, flag unphysical candidate sizes, and run machine learning late-fusion predictions. This ensures astronomers only schedule telescope follow-up time for candidates with a high probability of confirmation.

### Main Technologies
*   **Backend:** Python 3.12/3.13, FastAPI, SQLAlchemy, Uvicorn, SQLite, PyTorch (Deep Learning), Scikit-Learn / SciPy / Pandas (tabular pipeline and signal detrending).
*   **Frontend:** React 18, Next.js 14 (App Router), TypeScript, Tailwind CSS, TanStack Table, Recharts, Lucide React icons, and Framer Motion.

### Current Maturity
EEFN stands at a **Production-Ready Prototype** status. The pipeline fully implements database-backed ingestion, proper motion epoch translations, cross-catalog metric resolutions, and late-fusion inference. It features a complete web workstation and an optional immersive 3D zero-gravity simulation view mode.

### Overall Architecture Style
A decoupled **Model-View-Controller/REST API** architecture:
*   The **FastAPI backend** functions as the API engine, housing the SQLite database, the relational DB models, raw FITS/VizieR ingestion workers, and PyTorch inference engines.
*   The **Next.js frontend** serves as a single-page app framework, integrating layouts, sidebar navigation, custom SVG plotting components, and interactive canvas particle systems.

---

## 2. Repository Structure

The complete structure of the repository is detailed below:

```
D:\Gemini_Projects\EXO
├── backend
│   ├── app
│   │   ├── api
│   │   │   └── endpoints.py          # REST API endpoints (FastAPI)
│   │   ├── db
│   │   │   ├── models.py             # SQLAlchemy DB schemas
│   │   │   └── session.py            # SQLite database session creator
│   │   ├── ml
│   │   │   ├── deep_learning_pipeline.py # 4-Branch PyTorch DeepExoFusionNet model
│   │   │   ├── predict.py            # tabular RF and veto logic
│   │   │   ├── train_deep_learning.py# neural net training script
│   │   │   └── transit_pipeline.py   # light curve simulation & detrending math
│   │   ├── pipeline
│   │   │   └── ingest.py             # external catalog ingestion pipeline (TAP & X-Match)
│   │   └── config.py                 # backend configuration constants
│   ├── services
│   │   ├── alert_engine.py           # V2 quality scoring & rule alerts engine
│   │   └── audit_timeline.py         # entity resolution & chronology generation
│   ├── main.py                       # FastAPI application entry point
│   ├── seed_db.py                    # database seeding script (v2 schemas)
│   ├── requirements.txt              # backend Python dependencies
│   └── eefn.db                       # SQLite database file
├── frontend
│   ├── src
│   │   ├── app
│   │   │   ├── admin                 # Admin settings route
│   │   │   ├── ai-analysis           # AI Diagnostics workstation dashboard
│   │   │   ├── candidates            # Candidate registry listing table
│   │   │   │   └── [id]              # Candidate detailed verification dashboard
│   │   │   ├── compare               # Catalog cross reference comparison layout
│   │   │   ├── components            # Shared layout/visualization components
│   │   │   │   ├── AppSidebar.tsx    # Left-hand main navigation sidebar
│   │   │   │   ├── CentroidShiftMap.tsx # target pixel scatter plot
│   │   │   │   ├── NebulaCanvas.tsx  # zero-gravity space particle canvas
│   │   │   │   ├── ScientificUI.tsx  # badges, tags, and status cards
│   │   │   │   └── TransitLightCurve.tsx # dynamic U-shape transit curve plotter
│   │   │   ├── demo                  # API demo slide presentation tour
│   │   │   ├── fusion                # Consensus metrics dial dashboard
│   │   │   ├── helpers
│   │   │   │   └── astroHelpers.ts   # coordination math utilities
│   │   │   ├── types
│   │   │   │   └── types.ts          # TypeScript interfaces
│   │   │   ├── globals.css           # CSS 3D perspectives, float keyframes, styles
│   │   │   ├── layout.tsx            # Global framework layout wrapping
│   │   │   ├── page.tsx              # Mission overview dashboard landing page
│   │   │   └── TelemetryBar.tsx      # Top sticky live sync telemetry header
│   │   └── components                # Legacy shared component wrappers
│   ├── public
│   │   └── logo.png                  # Custom exoplanet branding logo asset
│   ├── package.json                  # Frontend dependencies
│   └── tailwind.config.js            # Tailwind utilities configuration
├── DATA_FLOW.md                      # Pipeline execution document
├── LIMITATIONS.md                    # Scientific and deployment caveats
├── PROJECT_OVERVIEW.md               # User-facing summary
└── reproduce_results.py              # Statistical validation script
```

### Purpose and Responsibilities by Folder

*   **`backend/app/api`:** Manages the REST endpoint routes, handles requests, and returns serialized Pydantic responses.
*   **`backend/app/db`:** Manages database models, tables, constraints, relationships, and engine initialization sessions.
*   **`backend/app/ml`:** Houses all machine learning modules, PyTorch CNN/MLP model definitions, RF pickle loading, simulated light curve generation, and phase folding algorithms.
*   **`backend/app/pipeline`:** Handles catalog retrieval. It queries NASA TAP and CDS Strasbourg X-Match, processes CSV streams, translates J2000 coordinates to J2016, and updates the database records.
*   **`backend/services`:** Implements rule-based exoplanet vetting calculations, creates diagnostic timeline event profiles, and handles manual coordinate overrides.
*   **`frontend/src/app`:** Orchestrates Routing (App Router), serves static layouts, handles responsive styles, and renders dynamic visuals (SVG vectors, canvas animation frame renders, and interactive forms).

---

## 3. Technology Stack

*   **Frontend:**
    *   *Framework:* Next.js 14.0.3 (App Router).
    *   *Language:* TypeScript.
    *   *Styling:* Tailwind CSS + CSS 3D Transforms (custom keyframe animations).
    *   *State Management:* React Hooks (`useState`, `useEffect`, `useCallback`, `useMemo`).
    *   *Icons:* Lucide React.
    *   *Visualizations:* Recharts (for trend areas), Custom SVG Renderers (for responsive plots), HTML5 Canvas 2D Context (for particle overlays).
*   **Backend:**
    *   *Framework:* FastAPI (Asynchronous Python REST API).
    *   *Server:* Uvicorn.
    *   *Database:* SQLite.
    *   *ORM:* SQLAlchemy (Declarative mapping and sessions).
*   **Machine Learning & Science:**
    *   *Deep Learning:* PyTorch (neural networks).
    *   *Tabular/Forest:* Scikit-Learn (imputation and Random Forest classifiers).
    *   *Scientific Math:* SciPy, NumPy, Pandas (light curve detrending, filtering, coordinate translations).
*   **Infrastructure & DevOps:**
    *   *Containerization:* Docker & Docker-Compose.
    *   *Build System:* Node.js npm (Frontend compile) / Python venv (Backend requirements).

---

## 4. Architecture

EEFN is structured in a clear, single-directional data flow from external catalogs down to frontend rendering widgets:

```
+-------------------------------------------------------------+
|                     Next.js 14 Frontend                     |
|  [V2 Overview Page]    [Registry Registry]    [Workstation] |
+------------------------------+------------------------------+
                               | (HTTPS REST Requests)
                               v
+-------------------------------------------------------------+
|                     FastAPI API Layer                       |
|   /api/v1/candidates    /candidates/{id}    /pipeline/run   |
+------------------------------+------------------------------+
                               | (Calls Business Logic)
                               v
+-------------------------------------------------------------+
|                Business Logic & Services                    |
|      [Alert Engine]         [Entity Resolution Timeline]    |
+------------------------------+------------------------------+
                               | (Invokes Inference)
                               v
+-------------------------------------------------------------+
|                     ML Pipeline & Vetting                   |
|  [RF tabular predict.py]    [4-Branch PyTorch Deep DL model] |
+------------------------------+------------------------------+
                               | (Reads / Writes Records)
                               v
+-------------------------------------------------------------+
|                   Database Layer (SQLite)                   |
|   HostStar    ExoplanetCandidate    MLPrediction   Metrics  |
+------------------------------+------------------------------+
                               ^
                               | (Synchronizes Catalogs)
+------------------------------+------------------------------+
|                 Evidence Ingestion Pipeline                 |
|   CDS X-Match Strasbourg API   <---->   NASA Exoplanet TAP  |
+-------------------------------------------------------------+
                               ^
                               | (External Sources)
+------------------------------+------------------------------+
|                      External Catalogs                      |
|          NASA Archive      Gaia DR3      APOGEE Spectra     |
+-------------------------------------------------------------+
```

### Layer Descriptions
1.  **Frontend View Layer:** Contains interactive scientific dashboards styled with Tailwind and CSS 3D transforms. It initiates API requests to display exoplanet candidates and telemetry.
2.  **API Layer:** FastAPI routers translate HTTP endpoints into database queries or asynchronous background tasks.
3.  **Business Logic Layer:** The AlertEngine checks physical consistency rules, flags discrepancies, and calculates letter grades (A-F).
4.  **ML Pipeline Layer:** Ingests phase-folded arrays and metadata. It applies temperature scaling calibration and runs late-fusion predictions.
5.  **Database/ORM Layer:** Houses relational schemas mapped via SQLAlchemy, storing targets, proper motions, and metrics.
6.  **Evidence Ingestion Layer:** Automates spatial cross-matching using CDS X-Match API and NASA Exoplanet Archive queries.

---

## 5. Backend Analysis

The backend contains the following Python modules:

### `app.db.models`
*   **Purpose:** Declares the database schema mapping to SQLite.
*   **Key Classes:** `HostStar`, `ExoplanetCandidate`, `CatalogSource`, `MeasurementHistory`, `AgreementMetrics`, `MLPrediction`.
*   **Interactions:** Forms the foundation of all repository reads and writes.

### `app.db.session`
*   **Purpose:** Initializes SQLAlchemy SQLite connections and session factory dependency hooks (`get_db`).

### `app.pipeline.ingest`
*   **Purpose:** Fetches external catalog parameters and translates J2000 stellar coordinates to J2016.0 epochs.
*   **Key Functions:** `post_with_retry`, `propagate_proper_motion`, `ingest_and_fuse_data`.
*   **Dependencies:** `requests`, `pandas`, `numpy`, `sqlalchemy`.

### `app.ml.transit_pipeline`
*   **Purpose:** Simulates exoplanet light curves, applies moving median detrending filters with transit masks, and calculates transit geometry metrics.
*   **Key Functions:** `generate_simulated_lightcurve`, `detrend_lightcurve`, `run_ai_classification`.

### `app.ml.deep_learning_pipeline`
*   **Purpose:** Defines the unified 4-branch multi-modal PyTorch model (`DeepExoFusionNet`) and pre-processes light curves.
*   **Key Classes:** `GlobalViewCNN`, `LocalViewCNN`, `CentroidSpatialCNN`, `StellarMetadataMLP`, `DeepExoFusionNet`, `DeepLearningVettingEngine`.
*   **Dependencies:** `torch`, `numpy`.

### `app.ml.predict`
*   **Purpose:** Runs tabular Random Forest predictions and executes physical size overrides (vetos).
*   **Key Classes:** `PredictionEngine` (loads `model_artifacts.pkl` and `model_weights.pth`).

### `services.alert_engine`
*   **Purpose:** Vets candidate properties, flags inconsistencies, and calculates the 0-100 evidence health score.
*   **Key Classes:** `AlertEngine`.

### `services.audit_timeline`
*   **Purpose:** Generates history, chronologies, and manual database coordinate override controls.
*   **Key Classes:** `EntityResolutionAudit`, `EvidenceTimeline`.

---

## 6. Frontend Analysis

The Next.js frontend uses React components to render the user workstation:

### Routing & UI Layout
*   **App Routing:** Organized inside `src/app`.
    *   `/` points to `page.tsx` (Mission Overview).
    *   `/candidates` points to `candidates/page.tsx` (Candidate Registry Listing).
    *   `/candidates/[id]` points to `candidates/[id]/page.tsx` (Detailed Vetting workstation).
    *   `/fusion` points to `fusion/page.tsx` (Consensus dials).
    *   `/ai-analysis` points to `ai-analysis/page.tsx` (AI Deep Learning diagnostics).
*   **Sticky Telemetry Header:** `TelemetryBar.tsx` pulls catalog sync datetimes and active alerts count, rendering them in a top bar.
*   **AppSidebar:** Renders the main left-hand menu, displaying the custom exoplanet project logo `logo.png`.

### Key Workstation Components
*   **`TransitLightCurve`:** An SVG-based plotter that maps time-series data, draws noise points, and overlays a blue transit fit line dynamically.
*   **`CentroidShiftMap`:** Computes in-transit vs out-of-transit stellar coordinates and draws offset scatter points and shift vectors.
*   **`NebulaCanvas`:** Runs an HTML5 Canvas 2D context particle simulation. When zero-gravity mode is active, it renders drifting stars and blue light trails.

---

## 7. Database Schema

The database layout is built using SQLite with SQLAlchemy mappings:

```
                     +-----------------------+
                     |      host_stars       |
                     +-----------------------+
                     | id (UUID, PK)         |
                     | hostname (String, Uq) |
                     | ra, dec (Float)       |
                     | parallax (Float)      |
                     | distance (Float)      |
                     | teff, logg, rad       |
                     | pm_ra, pm_dec, ruwe   |
                     +-----------+-----------+
                                 |
                                 | 1
                                 |
                                 | 1..*
                                 v
                     +-----------------------+
                     | exoplanet_candidates  |
                     +-----------------------+
                     | id (UUID, PK)         |
                     | host_id (UUID, FK) ---+
                     | tic_id (Integer)      |
                     | toi_id (Float, Uq)    |
                     | pl_name (String, Uq)  |
                     | disposition (String)  |
                     | orbper, rade, trandep |
                     | density_transit       |
                     | density_gaia          |
                     | health_score, grade   |
                     +-----+-----+-----+-----+
                           |     |     |
            +--------------+     |     +---------------+
            | 1                  | 1                   | 1
            |                    |                     |
            | 1                  | 1                   | 1..*
            v                    v                     v
+-----------------------+  +-------------------+  +-----------------------+
|   agreement_metrics   |  |  ml_predictions   |  |  measurement_history  |
+-----------------------+  +-------------------+  +-----------------------+
| id (UUID, PK)         |  | id (UUID, PK)     |  | id (UUID, PK)         |
| candidate_id (FK) ----+  | candidate_id (FK) |  | candidate_id (FK)     |
| teff_disagreement     |  | conf_probability  |  | source_id (UUID, FK)  |
| rad_disagreement      |  | prob_planet       |  | parameter_name        |
| dist_disagreement     |  | prob_eb, prob_act |  | value                 |
| ruwe, derived_rp_diff |  | prob_noise        |  | error_upper           |
| is_unphysical_rp      |  | feature_import    |  | error_lower           |
+-----------------------+  +-------------------+  +-----------------------+
                                                         | 1..*
                                                         |
                                                         | 1
                                                         v
                                                  +-----------------------+
                                                  |    catalog_sources    |
                                                  +-----------------------+
                                                  | id (UUID, PK)         |
                                                  | name (String, Uq)     |
                                                  | version (String)      |
                                                  | last_sync (DateTime)  |
                                                  +-----------------------+
```

---

## 8. Machine Learning

EEFN incorporates two machine learning pathways to analyze exoplanet candidates:

### 1. Tabular Evidence-Consistency Classifier (LightGBM; was a Random Forest until 2026-10-11 -- see `LIMITATIONS.md` section 3)
*   **Features Used:** 15 variables including `pl_insol`, `pl_eqt`, `pl_trandep`, `pl_rade`, `st_logg`, `st_rad`, `pl_trandurh`, `RUWE`, `st_dist`, `pl_orbper`, and catalog delta offsets.
*   **Model Storage:** Saved as a serialized pipeline in `model_artifacts.pkl`.
*   **Physics Override Veto:** Before returning the Random Forest score, `predict.py` calculates the physical planet radius using the Gaia stellar radius. If $R_p > 22.0 R_\oplus$, the score is overridden and capped at $3.5\%$ probability of confirmation.

### 2. Multi-Modal Late-Fusion Neural Network (`DeepExoFusionNet`) -- baseline only; light-curve vetting is now a gradient-boosted model on physics features, see `LIMITATIONS.md` section 7
Implements a 4-branch architecture in PyTorch:
*   **Global View CNN:** Extracts global phase-folded light curve features (2001 bins) to detect secondary eclipses.
*   **Local View CNN:** Ingests centered transit phase-folded light curves (201 bins) to analyze ingress/egress transit geometry.
*   **Centroid Spatial CNN:** Convolves target pixel centroid shifts (2 channels: $dx, dy$ x 201 bins) to identify background binary stars.
*   **Stellar Metadata MLP:** Processes 16 normalized catalog parameters (with planet size indicators stripped to prevent target leakage).
*   **Fusion Output:** Combines the branches into a 576-dimensional vector, returning calibrated probabilities across four classes: Planet, Eclipsing Binary, Stellar Activity, and Instrument Noise.

---

## 9. Evidence Fusion Pipeline

The core functionality of EEFN is its catalog harmonization and vetting pipeline:

```
       +---------------------------------------------+
       |   Ingest NASA TAP Exoplanet Candidate List  |
       +----------------------+----------------------+
                              |
                              v
       +---------------------------------------------+
       | Translate Coordinates (Proper Motion Epoch) |
       |        J2000.0   ----->   J2016.0           |
       +----------------------+----------------------+
                              |
                              v
       +---------------------------------------------+
       | CDS Strasbourg Cross-Match Server queries   |
       |      Gaia DR3 Source & Astrophysical DB     |
       +----------------------+----------------------+
                              |
                              v
       +---------------------------------------------+
       | Calculate Invariants:                       |
       |  - Recalculate Planet Size: R_* * sqrt(dp)  |
       |  - Compare Transit vs. Evolutionary Density |
       +----------------------+----------------------+
                              |
                              v
       +---------------------------------------------+
       | Run Decision Rules:                         |
       |  - Flag Unphysical Radius (> 22.0 R_Earth)  |
       |  - Flag Astrometric binary wiggle (RUWE > 1.4)|
       |  - Trigger parameter delta mismatches (>500K)|
       +----------------------+----------------------+
                              |
                              v
       +---------------------------------------------+
       |  Compute Evidence Health Score & Grade A-F  |
       +----------------------+----------------------+
                              |
                              v
       +---------------------------------------------+
       |     Execute Late-Fusion ML Predictions      |
       +---------------------------------------------+
```

---

## 10. External Integrations

*   **NASA Exoplanet Archive TAP Service:** Queried via HTTPS GET to retrieve orbital period, transit depth, and planetary parameters from the TFOP WG list.
*   **CDS X-Match Strasbourg Server:** Ingests CSV coordinate streams, performing spatial cross-matches against:
    *   *Gaia DR3 Source Catalog (`vizier:I/355/gaiadr3`):* Retrieves proper motion shifts, parallaxes, and RUWE metrics.
    *   *Gaia DR3 Astrophysical Parameters (`vizier:I/355/paramp`):* Retrieves stellar temperature ($T_{\text{eff}}$), radius ($R_*$), and stellar mass estimates.

---

## 11. Data Flow

Here is a walk-through of an execution sequence:

1.  **User Trigger:** The user clicks the **[INGEST & RUN AUDIT]** button on the workstation.
2.  **Frontend Dispatch:** The Next.js frontend sends a POST request to `http://127.0.0.1:8000/api/v1/pipeline/run?limit=50`.
3.  **FastAPI Worker:** FastAPI schedules an asynchronous background task running `ingest_and_fuse_data`.
4.  **Ingestion & Cross-Match:** The backend queries the NASA TAP server, propagates coordinate proper motions, and requests Gaia parameters from Strasbourg CDS.
5.  **Relational Insertion:** The server merges the datasets, computes physical invariants, flags anomalies, calculates health grades, and writes records to the SQLite database.
6.  **Inference Run:** The backend runs late-fusion predictions and saves the probability distributions to `ml_predictions`.
7.  **Client Fetch:** The Next.js client polls the endpoints, retrieves the updated candidate lists, and renders the V2 health grades, transit fits, and centroid offset charts.

---

## 12. Current Features

*   **Frontend Workstation:**
    *   Candidate list sorting and grade filtering.
    *   Dynamic SVG plotting for transit light curves.
    *   Target pixel centroid offset vector maps.
    *   Drifting canvas particle systems for the optional Zero-Gravity (Drift) view mode.
*   **Backend Server:**
    *   Asynchronous TAP/CDS VizieR cross-matching.
    *   Stellar proper motion epoch propagations.
    *   Physical radius and density consistency calculators.
    *   Calibrated Random Forest and 1D CNN classifier pipelines.
*   **Scientific & Analytics Engines:**
    *   Rule-based Alert engine (RUWE anomalies, size vetoes).
    *   Measurement history tracking for audit timelines.

---

## 13. Current Scientific Capabilities

*   **Epoch Corrected Coordinates:** Corrects stellar coordinates for proper motion epoch drift between J2000 (NASA) and J2016.0 (Gaia DR3) to prevent spatial mismatch errors.
*   **Planetary Radius Veto:** Re-calculates planetary radius using high-precision Gaia parallaxes to flag false positives where the host star's size was underestimated.
*   **Stellar Density Auditing:** Compares transit-derived stellar density against evolutionary stellar density. Large differences indicate grazing stellar eclipses rather than planetary transits.
*   **Astrometric Binary Identification:** Flags unit weight fit errors (RUWE > 1.4) to identify unresolved binary companion stars.

---

## 14. API Documentation

| Method | Endpoint | Input | Output | Description |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/v1/candidates` | Query params (disposition, limit) | `List[PlanetResponse]` | Retrieves exoplanet candidates, including their V2 health grades. |
| **GET** | `/api/v1/candidates/{id}` | Path parameter (TOI ID) | `CandidateProfileResponse` | Retrieves detailed candidate parameters, measurement history, and predictions. |
| **POST** | `/api/v1/pipeline/run` | Query parameters (limit) | `{"status": "success", ...}` | Asynchronously triggers the catalog cross-matching and ML pipeline. |
| **GET** | `/api/v1/catalog/health` | None | `dict` (sync, conflicts count) | Retrieves catalog health statistics and sync datetimes. |
| **GET** | `/api/v1/candidates/{id}/alerts` | Path parameter (TOI ID) | `List[Alert]` | Generates rule-based diagnostic alerts. |
| **GET** | `/api/v1/candidates/{id}/transit_pipeline` | Query parameters (noise, blending) | `dict` (flux, CNN predictions) | Runs live light curve simulations and deep learning classifications. |

---

## 15. Testing

The repository contains automated tests in `backend/tests`:
*   **`test_ingested_data.py`:** Validates proper motion propagation, derived radius computations, and database record insertions.
*   **`test_masked_detrend.py`:** Tests the transit-masked high-pass moving median filter to ensure in-transit data points do not distort the normalized baseline.
*   *Validation Scripts:* `reproduce_results.py` runs validation statistics on the Random Forest pipeline.

---

## 16. Complexity Assessment

*   **Lines of Code:**
    *   *Backend:* ~2,800 lines of Python code.
    *   *Frontend:* ~3,900 lines of Next.js, TSX, and Tailwind CSS code.
*   **Engineering Complexity:**
    *   *High Domain Complexity:* Requires combining astrophysics concepts (transit depth math, proper motion translations, evolutionary density) with software engineering patterns (asynchronous FastAPI task managers, WebGL-like canvas engines, late-fusion neural networks).
    *   *Interactive Drifting CSS Engine:* The transition between flat view and 3D floating space-glass view requires careful z-index management and smooth transition parameters.

---

## 17. Candidate Triton Task Opportunities

The following tasks identify realistic areas where implementation regressions or bugs could be introduced for Triton benchmarks:

### 1. Proper Motion Math Refactor
*   *Subsystem:* `backend/app/pipeline/ingest.py` (propagate_proper_motion)
*   *Difficulty:* Easy
*   *Cross-Module Reasoning:* No
*   *Triton Suitability:* Yes. Seeding a scale factor error (e.g. dividing by 3600 instead of 3,600,000) causes coordinate offsets during cross-matching, causing the CDS query to return the wrong stars.

### 2. Moving Median Mask Boundary Bug
*   *Subsystem:* `backend/app/ml/transit_pipeline.py` (detrend_lightcurve)
*   *Difficulty:* Medium
*   *Cross-Module Reasoning:* Yes (affects downstream classification)
*   *Triton Suitability:* Yes. Removing the transit mask from the median filter causes the transit dip itself to pull down the baseline trend. This dilutes the transit depth and causes the classifier to flag candidates as noise.

### 3. Neural Net Feature Mapping Discrepancy
*   *Subsystem:* `backend/app/ml/deep_learning_pipeline.py` (vet_candidate)
*   *Difficulty:* Medium
*   *Cross-Module Reasoning:* Yes
*   *Triton Suitability:* Yes. Reordering parameters in the 16-element metadata vector (e.g. swapping `st_rad` and `gaia_rad`) breaks PyTorch batch evaluations, leading to incorrect classifications.

### 4. Asynchronous Pipeline Rate-Limit Lock
*   *Subsystem:* `backend/app/pipeline/ingest.py` (post_with_retry)
*   *Difficulty:* Hard
*   *Cross-Module Reasoning:* Yes
*   *Triton Suitability:* Yes. Removing the backoff sleep logic or rate limit detection checks causes VizieR Strasbourg connections to fail under load, resulting in failed database imports.

### 5. Density Invariant Unit Translation Error
*   *Subsystem:* `backend/seed_db.py` / `ingest.py` (density_transit calculation)
*   *Difficulty:* Medium
*   *Cross-Module Reasoning:* Yes
*   *Triton Suitability:* Yes. Changing the transit duration unit from hours to seconds incorrectly in the density formula leads to calculated densities that differ from Gaia's by orders of magnitude, triggering false alert flags.

### 6. Ruwe Flag Boolean Inversion
*   *Subsystem:* `backend/services/alert_engine.py` (generate_alerts)
*   *Difficulty:* Easy
*   *Cross-Module Reasoning:* No
*   *Triton Suitability:* Yes. Changing `ruwe > 1.4` to `ruwe < 1.4` triggers false binary star alerts for single stars while letting actual binary systems pass without warnings.

### 7. Temperature Scaling Div-By-Zero
*   *Subsystem:* `backend/app/ml/deep_learning_pipeline.py` (DeepExoFusionNet classifier)
*   *Difficulty:* Easy
*   *Cross-Module Reasoning:* No
*   *Triton Suitability:* Yes. Setting the logit calibration temperature to zero causes division-by-zero errors during softmax probability calculations.

### 8. Phase Folding Sorting Shift
*   *Subsystem:* `backend/app/ml/deep_learning_pipeline.py` (preprocess_lightcurve)
*   *Difficulty:* Medium
*   *Cross-Module Reasoning:* Yes
*   *Triton Suitability:* Yes. Removing the phase sorting step (`np.argsort`) before running interpolation causes incorrect data mapping, which breaks the CNN classification.

### 9. SQLite DB Session Threading Leak
*   *Subsystem:* `backend/app/db/session.py`
*   *Difficulty:* Hard
*   *Cross-Module Reasoning:* Yes
*   *Triton Suitability:* Yes. Disabling SQLite thread-sharing options on uvicorn workers causes connection blockages and database lock exceptions during background sync runs.

### 10. Coordinate Dec Sexagesimal Conversion Overflow
*   *Subsystem:* `frontend/src/app/helpers/astroHelpers.ts` (decToHMS)
*   *Difficulty:* Easy
*   *Cross-Module Reasoning:* No
*   *Triton Suitability:* Yes. Introducing rounding errors in the sexagesimal coordinate conversion function causes coordinate displays to wrap around (e.g. showing 60 instead of incrementing the minute unit).

### 11. SVG Path Nan Dip Crash
*   *Subsystem:* `frontend/src/app/components/TransitLightCurve.tsx`
*   *Difficulty:* Medium
*   *Cross-Module Reasoning:* Yes
*   *Triton Suitability:* Yes. Failing to handle `NaN` transit depths or missing duration variables when drawing SVG paths causes browser render crashes.

### 12. Floating Animation perspective Translate overflow
*   *Subsystem:* `frontend/src/app/globals.css` (floatDetails keyframes)
*   *Difficulty:* Easy
*   *Cross-Module Reasoning:* No
*   *Triton Suitability:* Yes. Setting incorrect CSS z-axis translate values (`translateZ`) in zero-gravity mode causes elements to render behind the background canvas, making them invisible.

---

## 18. Final Assessment

### Is this repository substantially more complex than a typical CRUD application?
**Yes.** While a standard CRUD app simply manages database entries, EEFN processes physical invariants (like proper motion translations and stellar densities), detrends time-series data, and runs multi-modal deep learning models.

### Does it naturally require multi-module reasoning?
**Yes.** A change to the database schemas in `models.py` requires corresponding updates in the ingestion logic, the API serialization schemas, and the React data bindings.

### Would it make a strong foundation for difficult Triton software engineering tasks?
**Yes.** The combination of asynchronous tasks, Python mathematical libraries, PyTorch models, and a TypeScript frontend provides a robust testbed for evaluating an agent's technical skills.

### Subsystems most suitable for future benchmark creation:
*   **The Ingestion & Alignment Pipeline:** For testing coordinate translations and network retry logic.
*   **The Detrending and Physics Engine:** For testing numerical and signal processing calculations.
*   **The Multi-Modal DL Pipeline:** For testing tensor shape alignment, feature scaling, and neural network evaluations.
