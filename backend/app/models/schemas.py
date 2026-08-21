from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# DB models schemas representation

class StarBase(BaseModel):
    hostname: str
    ra: float
    dec: float
    parallax: Optional[float] = None
    distance: Optional[float] = None
    teff: Optional[float] = None
    logg: Optional[float] = None
    rad: Optional[float] = None
    mass: Optional[float] = None

class PlanetBase(BaseModel):
    pl_name: str
    tic_id: Optional[int] = None
    toi_id: Optional[float] = None
    disposition: str  # PC, CP, KP, FP, FA
    orbper: Optional[float] = None
    rade: Optional[float] = None
    trandep: Optional[float] = None
    trandur: Optional[float] = None
    insol: Optional[float] = None
    eqt: Optional[float] = None

class AgreementMetrics(BaseModel):
    teff_disagreement: float
    rad_disagreement: float
    dist_disagreement: float
    ruwe: Optional[float] = None
    derived_rp_diff: float
    is_unphysical_rp: bool
    completeness_score: float
    catalog_agreement_score: float

class PredictionOutputs(BaseModel):
    evidence_consistency_score: float
    followup_priority_score: float
    calculated_at: datetime

class CandidateProfile(BaseModel):
    planet: PlanetBase
    star: StarBase
    sources: List[str]
    measurement_history: Dict[str, Any]
    agreement_metrics: AgreementMetrics
    prediction: PredictionOutputs
