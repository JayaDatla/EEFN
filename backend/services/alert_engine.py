import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.db.models import ExoplanetCandidate, HostStar, AgreementMetrics, MeasurementHistory
from app.science.health import compute_health_score

class AlertEngine:
    def __init__(self, db: Session):
        self.db = db

    def generate_alerts(self, candidate_id: str) -> List[Dict[str, Any]]:
        """
        Runs the rule-based anomaly detection engine on a candidate exoplanet
        and host star, returning a list of detailed diagnostic alerts.
        """
        cand = self.db.query(ExoplanetCandidate).filter(ExoplanetCandidate.id == candidate_id).first()
        if not cand:
            return []

        star = cand.host
        metrics = cand.agreement_metrics
        
        alerts = []
        now = datetime.datetime.utcnow().isoformat()

        # Rule 1: Unphysical Derived Planet Radius
        # Transit depth in ppm, Rp in Earth radii.
        if star and star.rad and cand.trandep:
            # Derived planet radius using Gaia/Host star radius
            derived_rp = star.rad * (cand.trandep * 1e-6)**0.5 * 109.2
            if derived_rp > 22.0:  # > 2 Jupiter Radii
                alerts.append({
                    "id": f"ALERT_UNPHYSICAL_RP_{cand.pl_name}",
                    "category": "UNPHYSICAL_DERIVED_PLANET_RADIUS",
                    "severity": "CRITICAL",
                    "explanation": f"The derived planetary radius of {derived_rp:.2f} R_earth exceeds the physical limit for hydrogen-helium envelope planetary bodies (~22 R_earth / 2.0 R_jup).",
                    "affected_measurements": ["pl_trandep", "st_rad"],
                    "source_catalogs": ["NASA Exoplanet Archive", "Gaia DR3"],
                    "timestamp": now,
                    "likely_cause": "Binary companion / stellar contamination causing a grazing eclipse rather than a planet transit.",
                    "remediation": "Flag target as False Positive (Eclipsing Binary). Perform high-resolution imaging or radial velocity observations to identify stellar companion."
                })

        # Rule 2: High RUWE Anomaly
        if metrics and metrics.ruwe and metrics.ruwe > 1.4:
            alerts.append({
                "id": f"ALERT_HIGH_RUWE_{cand.pl_name}",
                "category": "HIGH_RUWE_ANOMALY",
                "severity": "HIGH",
                "explanation": f"Gaia DR3 Renormalised Unit Weight Error (RUWE) is {metrics.ruwe:.3f}, which exceeds the single-star astrometric standard threshold of 1.4.",
                "affected_measurements": ["RUWE"],
                "source_catalogs": ["Gaia DR3"],
                "timestamp": now,
                "likely_cause": "Astrometric wobble indicating a non-single star (unresolved stellar binary companion).",
                "remediation": "Conduct speckle interferometry or adaptive optics imaging to resolve the close stellar companion."
            })

        # Rule 3: Stellar Parameter Mismatch (Temperature)
        # We check the discrepancy between TESS TIC temperature and Gaia DR3 temperature
        if metrics and metrics.teff_disagreement and metrics.teff_disagreement > 500.0:
            alerts.append({
                "id": f"ALERT_TEFF_MISMATCH_{cand.pl_name}",
                "category": "STELLAR_PARAMETER_INCONSISTENCY",
                "severity": "HIGH",
                "explanation": f"Host star effective temperature mismatch between catalogs is {metrics.teff_disagreement:.1f} K (threshold: 500 K).",
                "affected_measurements": ["st_teff", "Teff"],
                "source_catalogs": ["TOI Catalog", "Gaia DR3"],
                "timestamp": now,
                "likely_cause": "Stellar blend or incorrect spectral classification in TIC.",
                "remediation": "Cross-match with high-resolution stellar spectra to calibrate temperature."
            })

        # Rule 4: Stellar Parameter Mismatch (Radius)
        if metrics and metrics.rad_disagreement and metrics.rad_disagreement > 0.25:
            alerts.append({
                "id": f"ALERT_RAD_MISMATCH_{cand.pl_name}",
                "category": "STELLAR_PARAMETER_INCONSISTENCY",
                "severity": "HIGH",
                "explanation": f"Host star radius mismatch between catalogs is {metrics.rad_disagreement:.3f} R_sun (threshold: 0.25 R_sun).",
                "affected_measurements": ["st_rad", "Rad"],
                "source_catalogs": ["TOI Catalog", "Gaia DR3"],
                "timestamp": now,
                "likely_cause": "Incorrect distance or reddening assumptions in TIC catalog stellar models.",
                "remediation": "Re-derive stellar models using Gaia DR3 parallaxes and spectrophotometry."
            })

        # Rule 5: Stellar Distance Mismatch
        if metrics and metrics.dist_disagreement and metrics.dist_disagreement > 100.0:
            alerts.append({
                "id": f"ALERT_DIST_MISMATCH_{cand.pl_name}",
                "category": "STELLAR_PARAMETER_INCONSISTENCY",
                "severity": "MEDIUM",
                "explanation": f"Host star distance mismatch is {metrics.dist_disagreement:.1f} pc (threshold: 100 pc).",
                "affected_measurements": ["st_dist", "Dist"],
                "source_catalogs": ["TOI Catalog", "Gaia DR3"],
                "timestamp": now,
                "likely_cause": "Parallax error or systematic shift in stellar distance calculations.",
                "remediation": "Verify proper motion alignment and catalog cross-match boundaries."
            })

        # Rule 6: Missing Gaia Counterpart
        if not star or star.parallax is None:
            alerts.append({
                "id": f"ALERT_MISSING_GAIA_{cand.pl_name}",
                "category": "MISSING_GAIA_COUNTERPART",
                "severity": "MEDIUM",
                "explanation": "No matching high-precision Gaia DR3 counterpart is recorded within the spatial cross-match search boundary.",
                "affected_measurements": ["parallax", "distance", "RUWE"],
                "source_catalogs": ["Gaia DR3"],
                "timestamp": now,
                "likely_cause": "Faint star below Gaia limiting magnitude (G > 21) or severe coordinate offset.",
                "remediation": "Perform manual spatial cone search on CDS VizieR using proper motion corrections."
            })

        # Rule 7: Classification Conflict
        # Check if exoplanet classification conflict exists between catalogs
        # (e.g. TOI says Candidate, but Exoplanet.eu or Simbad says False Positive)
        if cand.disposition == "FP" and "Candidate" in cand.pl_name:
            alerts.append({
                "id": f"ALERT_CLASSIFICATION_CONFLICT_{cand.pl_name}",
                "category": "CROSS_CATALOG_CLASSIFICATION_CONFLICT",
                "severity": "LOW",
                "explanation": f"Catalog classification conflict: TOI lists status as {cand.disposition} while object name reflects candidate.",
                "affected_measurements": ["disposition"],
                "source_catalogs": ["TOI Catalog", "NASA Archive"],
                "timestamp": now,
                "likely_cause": "Asynchronous database updates across community exoplanet archives.",
                "remediation": "Audit the latest publications on the target object to manually override database state."
            })

        return alerts

    def calculate_health_score(self, candidate_id: str) -> Dict[str, Any]:
        """
        Calculates a catalog-independent evidence health score (0-100) and returns the
        health score and associated letter grade. Formula lives in
        `app.science.health.compute_health_score` -- this must be the only place that
        formula is implemented (UPGRADE_PLAN.md C.3).
        """
        cand = self.db.query(ExoplanetCandidate).filter(ExoplanetCandidate.id == candidate_id).first()
        if not cand:
            return {"health_score": 0.0, "health_grade": "F", "factors": {}}

        result = compute_health_score(cand.agreement_metrics, cand)
        return {
            "health_score": result.score,
            "health_grade": result.grade,
            "factors": result.factors,
        }
