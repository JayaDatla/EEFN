"""
Identifier resolution (UPGRADE_PLAN.md G.2): "Never make a user hand-translate
TIC <-> TOI <-> Gaia source_id." Accepts a query in any common format
(`TOI-101.01`, `101.01`, `TIC 231663901`, `231663901`, `Gaia DR3 <source_id>`) and
returns every candidate sharing that identifier, with the full canonical ID set for
each so the caller never has to look up the others separately.
"""
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models import ExoplanetCandidate, HostStar

_TOI_PREFIX_RE = re.compile(r"^\s*toi[-\s]*", re.IGNORECASE)
_TIC_PREFIX_RE = re.compile(r"^\s*tic\s*", re.IGNORECASE)
_GAIA_PREFIX_RE = re.compile(r"^\s*gaia(\s*dr3)?\s*", re.IGNORECASE)


def _candidate_result(cand: ExoplanetCandidate, host: Optional[HostStar]) -> Dict[str, Any]:
    return {
        "pl_name": cand.pl_name,
        "toi_id": cand.toi_id,
        "tic_id": cand.tic_id,
        "gaia_dr3_source_id": host.gaia_dr3_source_id if host else None,
        "hostname": host.hostname if host else None,
        "disposition": cand.disposition,
    }


def resolve_identifier(db: Session, query: str) -> List[Dict[str, Any]]:
    """
    Returns a list of matching candidates (empty if none). A TOI ID match is unique
    (at most one row); a TIC ID or Gaia source_id can legitimately return multiple
    candidates, since one host star can have more than one TOI.
    """
    raw = query.strip()

    # Explicit prefix wins over guessing -- "TOI-101" and "TIC 101" must never resolve
    # to the same lookup just because they share digits.
    if _TOI_PREFIX_RE.match(raw):
        toi_str = _TOI_PREFIX_RE.sub("", raw)
        return _resolve_by_toi(db, toi_str)
    if _TIC_PREFIX_RE.match(raw):
        tic_str = _TIC_PREFIX_RE.sub("", raw)
        return _resolve_by_tic(db, tic_str)
    if _GAIA_PREFIX_RE.match(raw):
        gaia_str = _GAIA_PREFIX_RE.sub("", raw)
        return _resolve_by_gaia(db, gaia_str)

    # No prefix: a bare number with a decimal point is a TOI ID (TOI IDs are always
    # "<integer>.<planet-letter-as-digit>", e.g. 101.01); a bare integer is ambiguous
    # between TIC ID and Gaia source_id, so try both and merge results.
    if "." in raw:
        return _resolve_by_toi(db, raw)

    results = _resolve_by_tic(db, raw) + _resolve_by_gaia(db, raw)
    # De-duplicate (a bare integer could in principle match both a TIC ID and an
    # unrelated Gaia source_id -- keep both, just not the same candidate twice).
    seen = set()
    deduped = []
    for r in results:
        if r["pl_name"] not in seen:
            seen.add(r["pl_name"])
            deduped.append(r)
    return deduped


def _resolve_by_toi(db: Session, toi_str: str) -> List[Dict[str, Any]]:
    try:
        toi_val = float(toi_str)
    except ValueError:
        return []
    cand = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.toi_id == toi_val).first()
    if not cand:
        return []
    host = db.query(HostStar).filter(HostStar.id == cand.host_id).first()
    return [_candidate_result(cand, host)]


def _resolve_by_tic(db: Session, tic_str: str) -> List[Dict[str, Any]]:
    try:
        tic_val = int(tic_str)
    except ValueError:
        return []
    cands = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.tic_id == tic_val).all()
    results = []
    for cand in cands:
        host = db.query(HostStar).filter(HostStar.id == cand.host_id).first()
        results.append(_candidate_result(cand, host))
    return results


def _resolve_by_gaia(db: Session, gaia_str: str) -> List[Dict[str, Any]]:
    try:
        gaia_val = int(gaia_str)
    except ValueError:
        return []
    hosts = db.query(HostStar).filter(HostStar.gaia_dr3_source_id == gaia_val).all()
    results = []
    for host in hosts:
        for cand in host.candidates:
            results.append(_candidate_result(cand, host))
    return results
