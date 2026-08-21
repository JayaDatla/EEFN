from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import ExoplanetCandidate, HostStar, AgreementMetrics, MeasurementHistory, CatalogSource, DispositionChangeEvent
import datetime
from typing import List, Dict, Any, Optional

class EntityResolutionAudit:
    def __init__(self, db: Session):
        self.db = db

    def get_entity_profile(self, candidate_id: str) -> Dict[str, Any]:
        """
        Audit object identity resolutions across catalog identifier systems.

        Previously fabricated a fixed `resolution_confidence: 0.99` and a fixed
        "Match distance: 0.007 arcseconds" resolution_history entry for every
        candidate, regardless of whether -- or how well -- that candidate was
        actually cross-matched (found while fixing a crash in the sibling
        EvidenceTimeline class below). Neither number is derived from anything:
        the real CDS X-Match `angDist` value is never persisted to the DB, so
        there is no real per-candidate match distance to report. Reports only
        identifiers and match status that are actually stored.
        """
        cand = self.db.query(ExoplanetCandidate).filter(ExoplanetCandidate.id == candidate_id).first()
        if not cand:
            return {}

        star = cand.host
        gaia_matched = bool(star and star.gaia_dr3_source_id is not None)

        resolution_history = []
        if gaia_matched:
            earliest_gaia = (
                self.db.query(func.min(MeasurementHistory.measured_at))
                .join(CatalogSource, MeasurementHistory.source_id == CatalogSource.id)
                .filter(MeasurementHistory.candidate_id == cand.id, CatalogSource.name == "Gaia DR3")
                .scalar()
            )
            resolution_history.append({
                "timestamp": earliest_gaia.isoformat() + "Z" if earliest_gaia else None,
                "action": "AUTO_CROSSMATCH",
                "operator": "EEFN Ingestion Daemon",
                "details": f"TIC {cand.tic_id} cross-matched to Gaia DR3 source_id {star.gaia_dr3_source_id} "
                           f"via CDS X-Match (spatial cross-match; exact separation not persisted).",
            })

        return {
            "candidate_id": str(cand.id),
            "pl_name": cand.pl_name,
            "identifiers": {
                "tic_id": cand.tic_id,
                "toi_id": cand.toi_id,
                "gaia_dr3_source_id": star.gaia_dr3_source_id if star else None,
                "nasa_id": cand.pl_name,
            },
            # Real, not a fabricated constant: whether a Gaia DR3 source_id is actually
            # on record for this star's host -- the only cross-match fact we persist.
            "gaia_matched": gaia_matched,
            "resolution_history": resolution_history,
            "status": "AUTO_RESOLVED" if gaia_matched else "UNRESOLVED",
        }

    def manual_override_link(self, candidate_id: str, new_gaia_id: str) -> Dict[str, Any]:
        """
        Allows catalog curators to manually override coordinates match link.
        """
        cand = self.db.query(ExoplanetCandidate).filter(ExoplanetCandidate.id == candidate_id).first()
        if not cand:
            return {"status": "error", "message": "Candidate not found"}

        star = cand.host
        if star:
            old_hostname = star.hostname
            star.hostname = f"Gaia DR3 {new_gaia_id}"
            self.db.commit()

            return {
                "status": "success",
                "message": f"Successfully updated star identifier for exoplanet {cand.pl_name} from {old_hostname} to Gaia DR3 {new_gaia_id}.",
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        return {"status": "error", "message": "Host star not found"}


class EvidenceTimeline:
    def __init__(self, db: Session):
        self.db = db

    def get_timeline(self, candidate_id: str) -> List[Dict[str, Any]]:
        """
        Chronological audit trail of what EEFN itself has actually recorded for a
        candidate -- when each catalog's data was first captured, and any real
        disposition/health-grade transitions.

        Previously a fully fabricated narrative: hardcoded years (2018/2019/2022/
        2024/2025) attributed to *every* candidate regardless of when anything
        real happened for that star; fallback stellar values (parallax=2.56,
        Teff=6822.4 K, Rad=1.627 R_sun) presented as measurements whenever the
        real value was missing, rather than left absent; a duplicate, unguarded
        derived-radius formula (crashed with TypeError whenever `star` existed
        but `star.rad`/`cand.trandep` was None -- the crash that surfaced this
        whole file); and a hardcoded "(Eclipsing Binary alert resolved)" caption
        on every candidate's final event regardless of its actual disposition or
        whether anything was ever flagged. Replaced with real MeasurementHistory
        timestamps, the real disposition, and the shared derived_rp_gaia value
        (app.science.radius via ingest.py/predict.py) instead of recomputing it.
        """
        cand = self.db.query(ExoplanetCandidate).filter(ExoplanetCandidate.id == candidate_id).first()
        if not cand:
            return []

        star = cand.host
        metrics = cand.agreement_metrics

        timeline: List[Dict[str, Any]] = []

        # One event per catalog that actually has a recorded measurement for this
        # candidate, timestamped with the real earliest measurement we captured.
        rows = (
            self.db.query(CatalogSource.name, func.min(MeasurementHistory.measured_at))
            .join(MeasurementHistory, MeasurementHistory.source_id == CatalogSource.id)
            .filter(MeasurementHistory.candidate_id == cand.id)
            .group_by(CatalogSource.name)
            .order_by(func.min(MeasurementHistory.measured_at))
            .all()
        )
        for source_name, earliest in rows:
            ts = earliest.isoformat() if earliest else None
            timeline.append({
                "year": ts[:4] if ts else "unknown",
                "timestamp": ts,
                "event": "CATALOG_DATA_RECORDED",
                "catalog": source_name,
                "description": f"EEFN recorded {source_name} measurements for this candidate.",
                "value": None,
            })

        # Real catalog-disagreement evaluation, using the same shared derived-radius
        # value ingest.py/predict.py compute (app.science.radius) -- not a second,
        # independently-recomputed formula.
        if metrics:
            if metrics.is_unphysical_rp and metrics.derived_rp_gaia is not None:
                desc = (f"Catalog fusion flagged an unphysical derived planetary radius "
                        f"({metrics.derived_rp_gaia:.2f} R_earth, exceeds the 22.0 R_earth threshold).")
                status = "CRITICAL_CONFLICT"
            else:
                desc = "Catalog fusion evaluated cross-catalog stellar and transit parameters; no unphysical-radius conflict detected."
                status = "NO_CONFLICT"
            timeline.append({
                "year": "current",
                "timestamp": None,
                "event": "QUALITY_CONFLICT_EVALUATED",
                "catalog": "EEFN Fusion Engine",
                "description": desc,
                "value": f"Status: {status}",
            })

        # Real, timestamped disposition/health-grade transitions (H.3.5) -- never
        # inferred, only ever written by ingest.py when a re-sync's value genuinely
        # differs from what was already stored.
        changes = (
            self.db.query(DispositionChangeEvent)
            .filter(DispositionChangeEvent.candidate_id == cand.id)
            .order_by(DispositionChangeEvent.changed_at)
            .all()
        )
        for ch in changes:
            ts = ch.changed_at.isoformat() if ch.changed_at else None
            timeline.append({
                "year": ts[:4] if ts else "unknown",
                "timestamp": ts,
                "event": f"{ch.field_name.upper()}_CHANGED",
                "catalog": "EEFN Ingestion",
                "description": f"{ch.field_name.replace('_', ' ').title()} changed from {ch.old_value} to {ch.new_value} on re-sync.",
                "value": f"{ch.old_value} -> {ch.new_value}",
            })

        # Current, real disposition -- no invented resolution narrative.
        timeline.append({
            "year": "current",
            "timestamp": None,
            "event": "CURRENT_DISPOSITION",
            "catalog": "NASA Exoplanet Archive / TFOP",
            "description": f"Current disposition on record: {cand.disposition}.",
            "value": f"Disposition: {cand.disposition}",
        })

        return timeline
