"""
Framework-agnostic candidate-audit assembly (UPGRADE_PLAN.md D.4). This is the one
implementation behind both `GET /api/v1/candidates/{toi_id}` and the
`eefn.audit_candidate` library/CLI entry point, so the API and the installable
package can never silently drift into reporting different numbers for the same
candidate.
"""
from typing import Any, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models import ExoplanetCandidate, HostStar, AgreementMetrics, MLPrediction, MeasurementHistory
from app.science.tiers import compute_model_tier
from app.science.health import compute_health_score


def build_candidate_profile(db: Session, toi_id: float) -> Optional[Dict[str, Any]]:
    """Returns None if no candidate with this toi_id exists in the DB."""
    cand = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.toi_id == toi_id).first()
    if not cand:
        return None

    star = db.query(HostStar).filter(HostStar.id == cand.host_id).first()
    metrics = db.query(AgreementMetrics).filter(AgreementMetrics.candidate_id == cand.id).first()
    pred = db.query(MLPrediction).filter(MLPrediction.candidate_id == cand.id).first()

    measurement_history = {
        "stellar_radius": {"TOI Catalog": None, "Gaia DR3": None},
        "stellar_teff": {"TOI Catalog": None, "Gaia DR3": None},
        "distance": {"TOI Catalog": None, "Gaia DR3": None},
        "uncertainties": {
            "stellar_radius": {"TOI Catalog": None, "Gaia DR3": None},
            "stellar_teff": {"TOI Catalog": None, "Gaia DR3": None},
            "distance": {"TOI Catalog": None, "Gaia DR3": None},
        },
        # UPGRADE_PLAN.md H.3.2: provenance + query timestamp on every number --
        # when each source's value was actually last measured, not just what it is.
        "measured_at": {
            "stellar_radius": {"TOI Catalog": None, "Gaia DR3": None},
            "stellar_teff": {"TOI Catalog": None, "Gaia DR3": None},
            "distance": {"TOI Catalog": None, "Gaia DR3": None},
        },
    }

    tier_result = compute_model_tier(
        cand, star, has_real_light_curve=False,
        has_real_centroid=cand.centroid_is_real,
        has_real_spectroscopy=bool(star and star.spectroscopy_is_real),
    )
    health_result = compute_health_score(metrics, cand)

    measurements = db.query(MeasurementHistory).filter(MeasurementHistory.candidate_id == cand.id).all()
    for m in measurements:
        param = m.parameter_name
        src_name = m.source.name if m.source else None
        if src_name in ["TOI Catalog", "Gaia DR3"] and param in measurement_history:
            measurement_history[param][src_name] = m.value
            measurement_history["uncertainties"][param][src_name] = {
                "upper": m.error_upper,
                "lower": m.error_lower,
            }
            measurement_history["measured_at"][param][src_name] = m.measured_at.isoformat() if m.measured_at else None

    return {
        "planet": {
            "pl_name": cand.pl_name,
            "tic_id": cand.tic_id,
            "toi_id": cand.toi_id,
            "disposition": cand.disposition,
            "orbper": cand.orbper,
            "rade": cand.rade,
            "rade_err_upper": cand.rade_err_upper,
            "rade_err_lower": cand.rade_err_lower,
            "trandep": cand.trandep,
            "trandurh": cand.trandurh,
            "insol": cand.insol,
            "eqt": cand.eqt,
        },
        "star": {
            "hostname": star.hostname if star else f"TIC {cand.tic_id}",
            "ra": star.ra if star else 0.0,
            "dec": star.dec if star else 0.0,
            "parallax": star.parallax if star else None,
            "distance": star.distance if star else None,
            "teff": star.teff if star else None,
            "logg": star.logg if star else None,
            "rad": star.rad if star else None,
            "mass": star.mass if star else None,
        },
        "sources": ["NASA Exoplanet Archive", "Gaia DR3", "TOI Catalog"],
        "measurement_history": measurement_history,
        "agreement_metrics": {
            "teff_disagreement": metrics.teff_disagreement if metrics else 0.0,
            "rad_disagreement": metrics.rad_disagreement if metrics else 0.0,
            "dist_disagreement": metrics.dist_disagreement if metrics else 0.0,
            "ruwe": metrics.ruwe if metrics else None,
            "derived_rp_diff": metrics.derived_rp_diff if metrics else 0.0,
            "derived_rp_gaia": metrics.derived_rp_gaia if metrics else None,
            "derived_rp_gaia_err": metrics.derived_rp_gaia_err if metrics else None,
            "is_unphysical_rp": metrics.is_unphysical_rp if metrics else False,
            "completeness_score": metrics.completeness_score if metrics else 0.0,
            "catalog_agreement_score": metrics.catalog_agreement_score if metrics else 1.0,
        },
        "prediction": {
            "evidence_consistency_score": pred.evidence_consistency_score if pred else 0.5,
            "followup_priority_score": pred.followup_priority_score if pred else 0.5,
            "feature_importance": pred.feature_importance if pred else {},
            "calculated_at": pred.calculated_at if pred else datetime.utcnow(),
        },
        "model_tier": {
            "tier": tier_result.tier,
            "tier_name": tier_result.tier_name,
            "catalogs_available": tier_result.catalogs_available,
            "catalogs_missing": tier_result.catalogs_missing,
            "catalogs_total": tier_result.catalogs_total,
            "coverage_fraction": tier_result.coverage_fraction,
        },
        "health": {
            "score": cand.health_score if cand.health_score is not None else health_result.score,
            "grade": cand.health_grade if cand.health_grade else health_result.grade,
            "version": cand.health_score_version if cand.health_score_version else health_result.version,
            # UPGRADE_PLAN.md H.3.2: the real component breakdown from
            # app/science/health.py -- the single source of truth for this score
            # (C.3) -- recomputed live here so it can never be a second,
            # independently-drifting implementation the way a frontend
            # reimplementation of this formula would be.
            "factors": health_result.factors,
        },
    }
