import logging
import os
import pickle
import uuid
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, Union

from sqlalchemy.orm import Session
from app.db.models import ExoplanetCandidate, HostStar, AgreementMetrics, MLPrediction
from app.science.radius import compute_derived_planet_radius_earth

logger = logging.getLogger(__name__)

UNPHYSICAL_RP_THRESHOLD_EARTH_RADII = 22.0


class PredictionEngine:
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(current_dir, "model_artifacts.pkl")

        self.model = None
        self.imputer = None
        self.feature_names = []
        self.loaded = False

        if os.path.exists(model_path):
            try:
                with open(model_path, "rb") as f:
                    artifacts = pickle.load(f)
                self.model = artifacts["model"]
                self.imputer = artifacts["imputer"]
                self.feature_names = artifacts["features"]
                self.loaded = True
                logger.info("EEFN PredictionEngine loaded Random Forest model successfully.")
            except Exception as e:
                logger.error("Failed to load model artifacts (%s). Running in fallback mode -- "
                              "every prediction will report model_status=unavailable.", e)
        else:
            logger.warning("Running PredictionEngine in fallback mode (no model_artifacts.pkl found) -- "
                            "every prediction will report model_status=unavailable.")

    def _extract_raw_inputs(self, data: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """Pulls the raw catalog values needed to build the feature row, from either a
        DB-sourced dict (see predict_confirmation) or a caller-supplied raw dict. Values
        that aren't available are left as None -- callers must not invent defaults here,
        the SimpleImputer trained alongside the model is what handles missingness."""
        st_teff = data.get("st_teff")
        Teff = data.get("Teff", st_teff)
        st_rad = data.get("st_rad")
        Rad = data.get("Rad", st_rad)
        st_dist = data.get("st_dist")
        Dist = data.get("Dist", st_dist)
        st_tmag = data.get("st_tmag")
        Gmag = data.get("Gmag", st_tmag)

        return {
            "st_teff": st_teff, "Teff": Teff,
            "st_rad": st_rad, "Rad": Rad,
            "st_dist": st_dist, "Dist": Dist,
            "st_tmag": st_tmag, "Gmag": Gmag,
            "pl_trandep": data.get("pl_trandep"),
            "pl_rade": data.get("pl_rade"),
            "RUWE": data.get("RUWE"),
            "pl_orbper": data.get("pl_orbper"),
            "pl_trandurh": data.get("pl_trandurh"),
            "pl_insol": data.get("pl_insol"),
            "pl_eqt": data.get("pl_eqt"),
            "st_logg": data.get("st_logg"),
        }

    def build_feature_row(self, data: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """Reproduces, feature-for-feature, the engineering done in
        validation/scripts/train_and_serialize_model.py so inference sees exactly the
        columns the model was fit on. Missing inputs propagate as None -> NaN, which the
        trained median SimpleImputer handles; we never substitute a plausible-looking
        default ourselves."""
        eps = 1e-6
        raw = self._extract_raw_inputs(data)
        st_teff, Teff = raw["st_teff"], raw["Teff"]
        st_rad, Rad = raw["st_rad"], raw["Rad"]
        st_dist, Dist = raw["st_dist"], raw["Dist"]
        st_tmag, Gmag = raw["st_tmag"], raw["Gmag"]
        pl_trandep, pl_rade, RUWE = raw["pl_trandep"], raw["pl_rade"], raw["RUWE"]

        def diff(a, b):
            return abs(a - b) if a is not None and b is not None else None

        def rel(d, denom):
            return d / (denom + eps) if d is not None and denom is not None else None

        teff_diff = diff(st_teff, Teff)
        rad_diff = diff(st_rad, Rad)
        dist_diff = diff(st_dist, Dist)
        tmag_gmag_diff = diff(st_tmag, Gmag)

        # Shared with ingest.py via app.science.radius (UPGRADE_PLAN.md E.3) so the two
        # can never compute a different derived radius for the same inputs.
        derived_rp_gaia = compute_derived_planet_radius_earth(Rad, pl_trandep)
        derived_rp_diff = diff(derived_rp_gaia, pl_rade)

        is_unphysical_rp_gaia = (
            1 if (derived_rp_gaia is not None and derived_rp_gaia > UNPHYSICAL_RP_THRESHOLD_EARTH_RADII) else 0
        )
        high_ruwe = 1 if (RUWE is not None and RUWE > 1.4) else 0
        completeness = sum(
            1 for v in [st_teff, st_rad, st_dist, Teff, Rad, Dist, RUWE] if v is not None
        )

        return {
            "pl_orbper": raw["pl_orbper"],
            "pl_trandurh": raw["pl_trandurh"],
            "pl_trandep": pl_trandep,
            "pl_rade": pl_rade,
            "pl_insol": raw["pl_insol"],
            "pl_eqt": raw["pl_eqt"],
            "st_tmag": st_tmag,
            "st_teff": st_teff,
            "st_rad": st_rad,
            "st_logg": raw["st_logg"],
            "st_dist": st_dist,
            "teff_diff": teff_diff,
            "teff_diff_rel": rel(teff_diff, Teff),
            "rad_diff": rad_diff,
            "rad_diff_rel": rel(rad_diff, Rad),
            "dist_diff": dist_diff,
            "dist_diff_rel": rel(dist_diff, Dist),
            "tmag_gmag_diff": tmag_gmag_diff,
            "derived_rp_gaia": derived_rp_gaia,
            "derived_rp_diff": derived_rp_diff,
            "derived_rp_diff_rel": rel(derived_rp_diff, pl_rade),
            "is_unphysical_rp_gaia": is_unphysical_rp_gaia,
            "RUWE": RUWE,
            "high_ruwe": high_ruwe,
            "completeness": completeness,
        }

    def _rf_contributions(self, X_imputed: np.ndarray) -> Tuple[np.ndarray, float]:
        """Per-instance feature attribution for the RF's positive-class probability,
        computed by walking each tree's decision path and attributing the change in
        class-1 probability at each split to the feature that split was made on
        (the standard 'treeinterpreter' decomposition). This is derived directly from
        the trained trees, not a fabricated per-call heuristic."""
        n_features = X_imputed.shape[1]
        contributions = np.zeros(n_features)
        biases = []

        for tree in self.model.estimators_:
            t = tree.tree_
            leaf_path = tree.decision_path(X_imputed)
            node_index = leaf_path.indices[leaf_path.indptr[0]:leaf_path.indptr[1]]

            values = t.value[:, 0, :].astype(float)
            row_sums = values.sum(axis=1, keepdims=True)
            row_sums[row_sums == 0] = 1.0
            probs = values / row_sums

            positive_class_idx = 1 if probs.shape[1] > 1 else 0
            biases.append(probs[node_index[0], positive_class_idx])

            for i in range(len(node_index) - 1):
                cur_node, next_node = node_index[i], node_index[i + 1]
                feature = t.feature[cur_node]
                if feature >= 0:
                    contributions[feature] += (
                        probs[next_node, positive_class_idx] - probs[cur_node, positive_class_idx]
                    )

        n_trees = len(self.model.estimators_)
        return contributions / n_trees, float(np.mean(biases))

    def predict_confirmation(self, candidate_input: Union[str, uuid.UUID, Dict[str, Any]], db: Session = None) -> Dict[str, Any]:
        """
        Runs the trained Random Forest evidence-consistency classifier on a candidate's
        real feature vector. This does not read the candidate's own disposition label to
        produce its output -- see the regression test in tests/test_predict.py, which
        asserts the returned probability is identical for two feature-identical rows that
        differ only in `disposition`.
        """
        data = {}
        candidate_obj = None

        if db is not None and not isinstance(candidate_input, dict):
            candidate_obj = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.id == candidate_input).first()
            if not candidate_obj:
                return {"status": "error", "detail": f"Candidate ID {candidate_input} not found."}

            host_obj = candidate_obj.host

            data = {
                "st_teff": host_obj.teff if host_obj else None,
                "Teff": (host_obj.teff_spec if host_obj and host_obj.teff_spec is not None else (host_obj.teff if host_obj else None)),
                "st_rad": host_obj.rad if host_obj else None,
                "Rad": (host_obj.rad_spec if host_obj and host_obj.rad_spec is not None else (host_obj.rad if host_obj else None)),
                "st_dist": host_obj.distance if host_obj else None,
                "Dist": host_obj.distance if host_obj else None,
                # No TESS magnitude column exists in HostStar/ExoplanetCandidate today --
                # left unset (None) rather than a fabricated 10.0; the imputer handles it.
                "st_tmag": None,
                "Gmag": host_obj.g_mag if host_obj else None,
                "pl_trandep": candidate_obj.trandep,
                "pl_rade": candidate_obj.rade,
                "RUWE": host_obj.ruwe if host_obj else None,
                "pl_orbper": candidate_obj.orbper,
                "pl_trandurh": candidate_obj.trandurh,
                "pl_insol": candidate_obj.insol,
                "pl_eqt": candidate_obj.eqt,
                "st_logg": host_obj.logg if host_obj else None,
            }
        elif isinstance(candidate_input, dict):
            data = candidate_input

        feature_row = self.build_feature_row(data)
        derived_rp_gaia = feature_row["derived_rp_gaia"]
        is_unphysical = bool(feature_row["is_unphysical_rp_gaia"])

        if not self.loaded:
            return {
                "status": "error",
                "detail": "Model artifacts unavailable; no prediction produced.",
                "model_status": "unavailable",
            }

        X_row = pd.DataFrame([feature_row])[self.feature_names]
        X_imputed = self.imputer.transform(X_row)

        proba = self.model.predict_proba(X_imputed)[0]
        classes = list(self.model.classes_)
        positive_idx = classes.index(1) if 1 in classes else int(np.argmax(proba))
        evidence_score = float(proba[positive_idx])

        # Priority score: how urgently this candidate merits follow-up telescope time.
        # Deliberately distinct from evidence_score -- an unphysical-radius candidate is
        # unlikely to be a real planet AND not worth chasing, so both terms fall together
        # here; C.5 will change this multiplier to a softer, density-aware weighting.
        priority_score = evidence_score * (0.1 if is_unphysical else 1.0)

        contributions, bias = self._rf_contributions(X_imputed)
        contrib_by_feature = dict(zip(self.feature_names, contributions))
        top_contrib = dict(
            sorted(contrib_by_feature.items(), key=lambda kv: abs(kv[1]), reverse=True)[:5]
        )

        if db is not None and candidate_obj:
            pred_rec = db.query(MLPrediction).filter(MLPrediction.candidate_id == candidate_obj.id).first()

            if not pred_rec:
                pred_rec = MLPrediction(
                    candidate_id=candidate_obj.id,
                    evidence_consistency_score=evidence_score,
                    followup_priority_score=priority_score,
                    prob_planet=evidence_score,
                    feature_importance=top_contrib,
                )
                db.add(pred_rec)
            else:
                pred_rec.evidence_consistency_score = evidence_score
                pred_rec.followup_priority_score = priority_score
                pred_rec.prob_planet = evidence_score
                pred_rec.feature_importance = top_contrib

            db.commit()

        return {
            "evidence_consistency_score": evidence_score,
            "followup_priority_score": priority_score,
            "derived_rp_gaia": round(derived_rp_gaia, 3) if derived_rp_gaia is not None else None,
            "is_unphysical": is_unphysical,
            "feature_contributions": top_contrib,
            "model_bias": round(bias, 4),
            "status": "success",
        }


# Global instance for the FastAPI backend
predictor = PredictionEngine()
