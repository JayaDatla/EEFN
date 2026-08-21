export interface HostStar {
  hostname: string;
  ra: number;
  dec: number;
  parallax?: number | null;
  distance?: number | null;
  teff?: number | null;
  logg?: number | null;
  rad?: number | null;
  mass?: number | null;
  pm_ra?: number | null;
  pm_dec?: number | null;
  ruwe?: number | null;
  j_mag?: number | null;
  k_mag?: number | null;
  teff_spec?: number | null;
  fe_h?: number | null;
}

export interface AgreementMetrics {
  teff_disagreement: number | null;
  rad_disagreement: number | null;
  dist_disagreement: number | null;
  ruwe?: number | null;
  derived_rp_diff: number;
  is_unphysical_rp: boolean;
  completeness_score?: number;
  catalog_agreement_score: number;
}

export interface MLPrediction {
  evidence_consistency_score: number;
  followup_priority_score: number;
  prob_planet?: number | null;
  prob_eb?: number | null;
  prob_activity?: number | null;
  prob_noise?: number | null;
  feature_importance?: Record<string, number> | null;
  calculated_at?: string;
}

export interface CandidateV2 {
  id?: string;
  toi_id: number;
  tic_id: number;
  pl_name: string;
  disposition: string;
  orbper: number;
  rade: number;
  trandep: number;
  trandurh: number;
  insol: number;
  eqt: number;
  evidence_consistency_score?: number;
  followup_priority_score?: number;
}

export interface CandidateProfileResponse {
  planet: CandidateV2;
  star: HostStar;
  sources: string[];
  measurement_history?: any;
  agreement_metrics: AgreementMetrics;
  prediction: MLPrediction;
}
