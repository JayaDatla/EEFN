"""
Catalog parameter changes, derived from the append-only measurement ledger.

`record_measurement` (app/pipeline/ingest.py) writes a new MeasurementHistory row only when a catalog's
value for a (candidate, source, parameter) actually differs from the last one stored. So every row after
the first in a series is a real change, and the first row is just the baseline.

Honest limits, stated in the response so a client cannot mistake them:
* `changed_at` is when EEFN's ingestion SAW the new value, not when the catalog released it.
* The first value of a series is a baseline, never reported as a change.
* A change in a Gaia or TOI value means the upstream record changed or the cross-match picked a
  different row; this module cannot tell those two apart.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models import CatalogSource, ExoplanetCandidate, MeasurementHistory

# Gaia DR3, 2MASS and Pan-STARRS DR1 are released, frozen catalogs: a value for the same star never
# changes between ingestions. If it differs, EEFN matched a different row (or a different star), so it is
# a cross-match change, not a catalog revision. Only live tables (the TOI table / NASA Exoplanet Archive)
# genuinely revise values, and a new Gaia release (DR4) will arrive as a NEW source version.
FROZEN_SOURCES = ("Gaia DR3", "2MASS", "Pan-STARRS")


def classify_change(source_name: str) -> str:
    return "crossmatch_change" if source_name.startswith(FROZEN_SOURCES) else "catalog_update"


CAVEAT = ("changed_at is when EEFN first saw the new value, not the catalog release date. The first value "
          "recorded for a series is a baseline and is not listed. kind=catalog_update is a value that a live "
          "catalog revised; kind=crossmatch_change is a value from a frozen catalog (Gaia DR3, 2MASS, Pan-STARRS) "
          "that differs because EEFN matched a different row or star.")


def catalog_change_events(
    db: Session,
    since: Optional[datetime] = None,
    parameter: Optional[str] = None,
    toi_id: Optional[float] = None,
    limit: int = 200,
    kind: Optional[str] = None,
) -> Dict[str, Any]:
    q = (db.query(MeasurementHistory, ExoplanetCandidate, CatalogSource)
         .join(ExoplanetCandidate, ExoplanetCandidate.id == MeasurementHistory.candidate_id)
         .join(CatalogSource, CatalogSource.id == MeasurementHistory.source_id))
    if parameter:
        q = q.filter(MeasurementHistory.parameter_name == parameter)
    if toi_id is not None:
        q = q.filter(ExoplanetCandidate.toi_id == toi_id)
    rows = q.order_by(MeasurementHistory.candidate_id, MeasurementHistory.source_id,
                      MeasurementHistory.parameter_name, MeasurementHistory.measured_at).all()

    events: List[Dict[str, Any]] = []
    prev_key, prev_val = None, None
    for m, cand, src in rows:
        key = (m.candidate_id, m.source_id, m.parameter_name)
        if key == prev_key and prev_val is not None:
            change = m.value - prev_val
            events.append({
                "toi_id": cand.toi_id, "pl_name": cand.pl_name, "source": src.name,
                "parameter": m.parameter_name, "old_value": prev_val, "new_value": m.value,
                "relative_change": (change / abs(prev_val)) if prev_val else None,
                "kind": classify_change(src.name),
                "changed_at": m.measured_at,
            })
        prev_key, prev_val = key, m.value

    if since is not None:
        events = [e for e in events if e["changed_at"] and e["changed_at"] > since]
    by_kind: Dict[str, int] = {}
    for e in events:
        by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + 1
    if kind:
        events = [e for e in events if e["kind"] == kind]
    events.sort(key=lambda e: e["changed_at"] or datetime.min, reverse=True)
    return {"count": len(events), "counts_by_kind": by_kind, "events": events[:limit], "caveat": CAVEAT}
