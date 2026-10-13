import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, Integer, BigInteger, Boolean, DateTime, ForeignKey, JSON, Uuid
from sqlalchemy.orm import relationship

from app.db.session import Base


class HostStar(Base):
    __tablename__ = "host_stars"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hostname = Column(String, unique=True, nullable=False)
    ra = Column(Float, nullable=False)
    dec = Column(Float, nullable=False)
    parallax = Column(Float, nullable=True)
    distance = Column(Float, nullable=True)
    teff = Column(Float, nullable=True)
    logg = Column(Float, nullable=True)
    rad = Column(Float, nullable=True)
    mass = Column(Float, nullable=True)

    # The TOI table's own host-star values (TIC-derived). teff/logg/rad/distance above are the
    # Gaia DR3 values; the catalog-disagreement features compare the two, so serving must be able
    # to see both. Without these columns the served model compared Gaia against itself (diffs 0).
    toi_teff = Column(Float, nullable=True)
    toi_rad = Column(Float, nullable=True)
    toi_dist = Column(Float, nullable=True)
    toi_logg = Column(Float, nullable=True)

    pm_ra = Column(Float, nullable=True)       # Gaia proper motion RA (mas/yr)
    pm_dec = Column(Float, nullable=True)      # Gaia proper motion Dec (mas/yr)
    ruwe = Column(Float, nullable=True)        # Gaia DR3 astrometric fit quality (>1.4 = binary wobble)

    # UPGRADE_PLAN.md D.1: used to cross-reference a host star's Gaia DR3 record
    # directly (TIC/TOI <-> Gaia DR3 source_id resolution, G.5).
    gaia_dr3_source_id = Column(BigInteger, nullable=True, index=True)

    # UPGRADE_PLAN.md F.5: 2MASS photometry (vizier:II/246/out)
    j_mag = Column(Float, nullable=True)
    h_mag = Column(Float, nullable=True)
    k_mag = Column(Float, nullable=True)

    # UPGRADE_PLAN.md F.5: Pan-STARRS photometry (vizier:II/349/ps1)
    g_mag = Column(Float, nullable=True)
    r_mag = Column(Float, nullable=True)
    i_mag = Column(Float, nullable=True)
    z_mag = Column(Float, nullable=True)
    y_mag = Column(Float, nullable=True)

    # UPGRADE_PLAN.md F.7: spectroscopy (APOGEE-2/GALAH/LAMOST). seed_db.py fabricates
    # plausible values for these four fields with no real ingestion path -- see
    # spectroscopy_is_real below and app/pipeline/spectroscopy.py's module docstring for
    # why field-presence alone must never be read as "this came from a real survey."
    teff_spec = Column(Float, nullable=True)
    rad_spec = Column(Float, nullable=True)
    fe_h = Column(Float, nullable=True)        # Metallicity [Fe/H] (dex)
    alpha_fe = Column(Float, nullable=True)    # Alpha-element abundance [alpha/Fe] (dex)
    spectroscopy_is_real = Column(Boolean, default=False, nullable=False)
    spectroscopy_source = Column(String, nullable=True)      # e.g. "APOGEE-2 DR17 (VizieR III/286)"
    spectroscopy_computed_at = Column(DateTime, nullable=True)
    spectroscopy_attempted_at = Column(DateTime, nullable=True)  # last sync attempt, matched or not

    created_at = Column(DateTime, default=datetime.utcnow)

    candidates = relationship("ExoplanetCandidate", back_populates="host")


class ExoplanetCandidate(Base):
    __tablename__ = "exoplanet_candidates"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    host_id = Column(Uuid(as_uuid=True), ForeignKey("host_stars.id"), nullable=False)
    tic_id = Column(Integer, nullable=True, index=True)
    toi_id = Column(Float, unique=True, nullable=True, index=True)
    pl_name = Column(String, unique=True, nullable=False)
    disposition = Column(String, nullable=False, index=True)  # PC, CP, KP, FP, FA
    orbper = Column(Float, nullable=True)
    rade = Column(Float, nullable=True)
    rade_err_upper = Column(Float, nullable=True)  # pl_radeerr1, catalog-quoted +error (R_Earth)
    rade_err_lower = Column(Float, nullable=True)  # pl_radeerr2, catalog-quoted -error (R_Earth)
    trandep = Column(Float, nullable=True)
    trandurh = Column(Float, nullable=True)
    insol = Column(Float, nullable=True)
    eqt = Column(Float, nullable=True)
    tranmid = Column(Float, nullable=True)  # pl_tranmid, BJD_TDB -- transit midpoint epoch, powers the observability-tonight filter (H.3.1)

    # --- ExoFusion-Net v2 Diagnostics & Health Engine ---
    density_transit = Column(Float, nullable=True)          # Transit-derived density (g/cm^3)
    density_gaia = Column(Float, nullable=True)             # Gaia evolutionary density (g/cm^3)
    density_discrepancy_sigma = Column(Float, nullable=True) # Density delta in sigmas
    centroid_shift_max = Column(Float, nullable=True)        # Max photocenter drift (arcsec)
    has_centroid_dip = Column(Boolean, default=False)       # True if centroid shifts synchronously
    # UPGRADE_PLAN.md F.6: seed_db.py fabricates plausible centroid_shift_max/has_centroid_dip
    # values with no real ingestion path -- centroid_is_real distinguishes an actual MAST TPF
    # measurement (app/pipeline/mast_centroid.py) from that fabricated demo data, and is the
    # flag tiers.py's has_real_centroid must be sourced from, never field-presence alone.
    centroid_is_real = Column(Boolean, default=False, nullable=False)
    centroid_significance_sigma = Column(Float, nullable=True)   # in-transit vs out-of-transit offset / its standard error
    centroid_sector = Column(Integer, nullable=True)             # TESS sector the TPF was downloaded from
    centroid_computed_at = Column(DateTime, nullable=True)
    centroid_attempted_at = Column(DateTime, nullable=True)      # last sync attempt, measured or not
    # centroid_shift_max is the raw photocentre shift (arcsec) -- tiny by construction, it scales
    # with transit depth. These two are the interpretable quantity: shift / depth = how far from
    # the target the dimming source sits (app/pipeline/mast_centroid.py).
    centroid_implied_offset_arcsec = Column(Float, nullable=True)
    centroid_implied_offset_err_arcsec = Column(Float, nullable=True)
    centroid_status = Column(String, nullable=True)              # measured | no_epoch | no_measurement
    # Real-TESS-light-curve vetting (app/ml/lightcurve_vetter.py, run by the scheduled
    # sync in app/pipeline/real_sync.py). lc_vetting_json holds class probabilities, the
    # feature values the model saw, the sectors used and the 2001/201-bin views the UI plots.
    lc_vetting_json = Column(JSON, nullable=True)
    lc_vetting_status = Column(String, nullable=True)            # vetted | no_lightcurve | unusable | no_epoch
    lc_vetting_at = Column(DateTime, nullable=True)
    lc_vetting_attempted_at = Column(DateTime, nullable=True)
    # Phase-folded, 201-bin (dx, dy) arrays in the same local-view window convention as
    # deep_learning_pipeline.py's CENTROID_BINS/preprocess_lightcurve -- this is what
    # actually lets a real measurement reach CentroidSpatialCNN at inference (F.6's DoD
    # requires "feeds CentroidSpatialCNN", not just a summary statistic stored for the
    # health/alert layer).
    centroid_dx_json = Column(JSON, nullable=True)
    centroid_dy_json = Column(JSON, nullable=True)
    health_score = Column(Float, nullable=True)             # 0 to 100 Evidence Health Score
    health_grade = Column(String, nullable=True, index=True) # Letter Grade A, B, C, D, F
    health_score_version = Column(String, nullable=True)    # app.science.health.HEALTH_SCORE_VERSION at calc time
    query_failed = Column(Boolean, default=False)           # True if external catalog query timed out

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    host = relationship("HostStar", back_populates="candidates")
    measurements = relationship("MeasurementHistory", back_populates="candidate")
    agreement_metrics = relationship("AgreementMetrics", back_populates="candidate", uselist=False)
    prediction = relationship("MLPrediction", back_populates="candidate", uselist=False)


class CatalogSource(Base):
    __tablename__ = "catalog_sources"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    version = Column(String, nullable=True)
    last_sync = Column(DateTime, default=datetime.utcnow)


class MeasurementHistory(Base):
    __tablename__ = "measurement_history"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(Uuid(as_uuid=True), ForeignKey("exoplanet_candidates.id"), nullable=False)
    source_id = Column(Uuid(as_uuid=True), ForeignKey("catalog_sources.id"), nullable=False)
    parameter_name = Column(String, nullable=False)  # teff, rad, distance, period, depth, etc.
    value = Column(Float, nullable=False)
    error_upper = Column(Float, nullable=True)
    error_lower = Column(Float, nullable=True)
    measured_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("ExoplanetCandidate", back_populates="measurements")
    source = relationship("CatalogSource")


class AgreementMetrics(Base):
    __tablename__ = "agreement_metrics"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(Uuid(as_uuid=True), ForeignKey("exoplanet_candidates.id"), unique=True, nullable=False)
    # Nullable, not defaulted to 0.0: a missing Gaia (or TOI) value means the
    # disagreement is genuinely unknown, not "confirmed zero difference" -- see
    # ingest.py's diff() helper. A prior version of ingest.py wrote 0.0 here
    # whenever either side was missing, which made "no Gaia match at all" render
    # identically to "measured, perfect agreement" on the fusion/compare pages.
    teff_disagreement = Column(Float, nullable=True)
    rad_disagreement = Column(Float, nullable=True)
    dist_disagreement = Column(Float, nullable=True)
    ruwe = Column(Float, nullable=True)
    derived_rp_diff = Column(Float, nullable=True)
    derived_rp_gaia = Column(Float, nullable=True)      # Gaia-transit-derived planet radius (R_Earth)
    derived_rp_gaia_err = Column(Float, nullable=True)  # propagated uncertainty on derived_rp_gaia
    is_unphysical_rp = Column(Boolean, nullable=False)
    completeness_score = Column(Float, nullable=False)
    catalog_agreement_score = Column(Float, nullable=False)

    candidate = relationship("ExoplanetCandidate", back_populates="agreement_metrics")


class MLPrediction(Base):
    __tablename__ = "ml_predictions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(Uuid(as_uuid=True), ForeignKey("exoplanet_candidates.id"), unique=True, nullable=False)
    evidence_consistency_score = Column(Float, nullable=False)  # UPGRADE_PLAN.md C.7 (was confirmation_probability)
    followup_priority_score = Column(Float, nullable=False)
    prob_planet = Column(Float, nullable=True)
    prob_eb = Column(Float, nullable=True)
    prob_activity = Column(Float, nullable=True)
    prob_noise = Column(Float, nullable=True)
    integrated_gradients = Column(JSON, nullable=True)
    feature_importance = Column(JSON, nullable=True)
    model_version = Column(String, nullable=True)   # which artifact produced this score
    calculated_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("ExoplanetCandidate", back_populates="prediction")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    # UPGRADE_PLAN.md D.2: one row per ingestion execution, so every stored candidate
    # value is traceable to the exact run (catalogs/versions used, targets processed,
    # failures, duration) that produced it -- not just a bare "last updated" timestamp.
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    arq_job_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False)  # queued, running, success, error, cancelled
    limit_requested = Column(Integer, nullable=False)
    catalogs_used = Column(JSON, nullable=True)
    catalog_versions = Column(JSON, nullable=True)
    targets_processed = Column(Integer, nullable=True)
    failures = Column(JSON, nullable=True)
    error_detail = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)


class DispositionChangeEvent(Base):
    __tablename__ = "disposition_change_events"

    # UPGRADE_PLAN.md H.3.5: the diff/"what changed" view -- "these N targets changed
    # disposition or grade since your last sync." A real, timestamped ledger of actual
    # transitions, written by ingest.py's upsert path whenever a re-ingested
    # candidate's disposition or health_grade genuinely differs from what was already
    # stored, never inferred or backfilled after the fact.
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(Uuid(as_uuid=True), ForeignKey("exoplanet_candidates.id"), nullable=False)
    toi_id = Column(Float, nullable=True, index=True)
    pl_name = Column(String, nullable=False)
    field_name = Column(String, nullable=False)  # "disposition" or "health_grade"
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow, index=True)
