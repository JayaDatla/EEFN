"""
VOTable/TAP export (UPGRADE_PLAN.md G, Phase 4 -- Interoperability): "How astronomers
already consume data (TOPCAT, Aladin, astroquery) -- near-free interop." This is the
one implementation behind both `GET /api/v1/candidates/export` and the `eefn export
--format votable` CLI command, same shared-source-of-truth pattern as app/audit.py.
"""
import io
from typing import List, Optional

import astropy.units as u
from astropy.table import Table
from sqlalchemy.orm import Session

from app.db.models import ExoplanetCandidate, MLPrediction

# (column, unit, description) -- VOTable FIELD metadata a real client (TOPCAT, Aladin)
# will actually display, not just bare numbers. Units are real astropy.units objects,
# not bare strings -- "ppm" and "Earth radius" are not valid VOUnit strings and
# astropy warns loudly (and a real VO client may reject the field) if given them as
# text; there's no standard VOUnit for parts-per-million so trandep is left
# dimensionless with the unit noted in its description instead.
_COLUMNS = [
    ("pl_name", None, "EEFN candidate identifier (TOI-<id>)"),
    ("tic_id", None, "TESS Input Catalog ID"),
    ("toi_id", None, "TESS Object of Interest ID"),
    ("disposition", None, "TFOPWG disposition (CP/KP/PC/FP/FA)"),
    ("orbper", u.day, "Orbital period"),
    ("rade", u.earthRad, "Catalog-reported planet radius"),
    ("rade_err_upper", u.earthRad, "Catalog planet radius, +error"),
    ("rade_err_lower", u.earthRad, "Catalog planet radius, -error"),
    ("trandep", None, "Transit depth, ppm"),
    ("trandurh", u.hour, "Transit duration"),
    ("health_score", None, "EEFN evidence health score (0-100)"),
    ("health_grade", None, "EEFN evidence health letter grade (A-F)"),
    ("evidence_consistency_score", None, "EEFN Random Forest evidence-consistency score (0-1)"),
]


def build_candidates_table(
    db: Session, disposition: Optional[str] = None, limit: int = 5000, toi_ids: Optional[List[float]] = None
) -> Table:
    """Real astropy Table backing both the VOTable export and (via to_pandas) any
    future CSV/FITS export -- one query, one column list, reused everywhere.
    `toi_ids` (UPGRADE_PLAN.md H.3.4 batch workflow) restricts the table to exactly
    those TOIs, in the order supplied by the caller -- not silently truncated to
    whichever `toi_ids` happen to also satisfy `limit`, since a batch upload's
    output should contain every real match, not a re-paginated subset of it."""
    query = db.query(ExoplanetCandidate, MLPrediction).outerjoin(
        MLPrediction, MLPrediction.candidate_id == ExoplanetCandidate.id
    )
    if disposition:
        query = query.filter(ExoplanetCandidate.disposition == disposition)
    if toi_ids:
        query = query.filter(ExoplanetCandidate.toi_id.in_(toi_ids))
        rows = query.order_by(ExoplanetCandidate.toi_id.asc()).all()
    else:
        rows = query.order_by(ExoplanetCandidate.toi_id.asc()).limit(limit).all()

    data = {col: [] for col, _, _ in _COLUMNS}
    for cand, pred in rows:
        data["pl_name"].append(cand.pl_name)
        data["tic_id"].append(cand.tic_id if cand.tic_id is not None else -1)
        data["toi_id"].append(cand.toi_id if cand.toi_id is not None else float("nan"))
        data["disposition"].append(cand.disposition or "")
        data["orbper"].append(cand.orbper if cand.orbper is not None else float("nan"))
        data["rade"].append(cand.rade if cand.rade is not None else float("nan"))
        data["rade_err_upper"].append(cand.rade_err_upper if cand.rade_err_upper is not None else float("nan"))
        data["rade_err_lower"].append(cand.rade_err_lower if cand.rade_err_lower is not None else float("nan"))
        data["trandep"].append(cand.trandep if cand.trandep is not None else float("nan"))
        data["trandurh"].append(cand.trandurh if cand.trandurh is not None else float("nan"))
        data["health_score"].append(cand.health_score if cand.health_score is not None else float("nan"))
        data["health_grade"].append(cand.health_grade or "")
        data["evidence_consistency_score"].append(
            pred.evidence_consistency_score if pred and pred.evidence_consistency_score is not None else float("nan")
        )

    table = Table(data)
    for col, unit, description in _COLUMNS:
        if unit:
            table[col].unit = unit
        table[col].description = description
    return table


def build_candidates_votable_bytes(
    db: Session, disposition: Optional[str] = None, limit: int = 5000, toi_ids: Optional[List[float]] = None
) -> bytes:
    table = build_candidates_table(db, disposition=disposition, limit=limit, toi_ids=toi_ids)
    buf = io.BytesIO()
    table.write(buf, format="votable")
    return buf.getvalue()
