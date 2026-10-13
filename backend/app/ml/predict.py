import logging
import math
import os
import pickle

import sklearn
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
        self.model_version = None

        if os.path.exists(model_path):
            try:
                with open(model_path, "rb") as f:
                    artifacts = pickle.load(f)
                self.model = artifacts["model"]
                self.imputer = artifacts["imputer"]
                self.feature_names = artifacts["features"]
                self.model_version = self._read_model_version(model_path)
                trained_with = artifacts.get("sklearn_version")
                if trained_with and trained_with != sklearn.__version__:
                    logger.warning("model_artifacts.pkl was trained with scikit-learn %s but %s is "
                                   "installed; retrain via validation/scripts/train_and_serialize_model.py "
                                   "if predictions misbehave.", trained_with, sklearn.__version__)
                self.loaded = True
                logger.info("EEFN PredictionEngine loaded Random Forest model successfully.")
            except Exception as e:
                logger.error("Failed to load model artifacts (%s). Running in fallback mode -- "
                              "every prediction will report model_status=unavailable.", e)
        else:
            logger.warning("Running PredictionEngine in fallback mode (no model_artifacts.pkl found) -- "
                            "every prediction will report model_status=unavailable.")

    @staticmethod
    def _read_model_version(model_path: str) -> Optional[str]:
        """Version of the artifact, from the metrics file written by the same training run."""
        import json
        try:
            with open(os.path.join(os.path.dirname(model_path), "model_metrics.json")) as f:
                return json.load(f).get("model_version")
        except Exception:
            return None

    def _extract_raw_inputs(self, data: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """Pulls the raw catalog values needed to build the feature row, from either a
        DB-sourced dict (see predict_confirmation) or a caller-supplied raw dict. Values
        that aren't available are left as None -- callers must not invent defaults here,
        the SimpleImputer trained alongside the model is what handles missingness."""
        st_teff = data.get("st_teff")
        Teff = data.get("Teff")
        st_rad = data.get("st_rad")
        Rad = data.get("Rad")
        st_dist = data.get("st_dist")
        Dist = data.get("Dist")

        return {
            "st_teff": st_teff, "Teff": Teff,
            "st_rad": st_rad, "Rad": Rad,
            "st_dist": st_dist, "Dist": Dist,
            "Plx": data.get("Plx"),
            "Jmag": data.get("Jmag"), "Hmag": data.get("Hmag"), "Kmag": data.get("Kmag"),
            "PS_gmag": data.get("PS_gmag"), "PS_rmag": data.get("PS_rmag"),
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
        pl_trandep, pl_rade, RUWE = raw["pl_trandep"], raw["pl_rade"], raw["RUWE"]

        def diff(a, b):
            return abs(a - b) if a is not None and b is not None else None

        def rel(d, denom):
            return d / (denom + eps) if d is not None and denom is not None else None

        teff_diff = diff(st_teff, Teff)
        rad_diff = diff(st_rad, Rad)
        dist_diff = diff(st_dist, Dist)

        def colour(a, b):
            return a - b if a is not None and b is not None else None

        # abs_K from the Gaia parallax (mas): M = m + 5*log10(plx_mas) - 10. An independent
        # luminosity-class indicator (giants vs dwarfs) to hold against the catalog radius.
        Plx, Kmag = raw["Plx"], raw["Kmag"]
        abs_K = (Kmag + 5.0 * math.log10(max(Plx, 1e-3)) - 10.0) if Plx is not None and Kmag is not None else None

        # Shared with ingest.py via app.science.radius (UPGRADE_PLAN.md E.3) so the two
        # can never compute a different derived radius for the same inputs.
        derived_rp_gaia = compute_derived_planet_radius_earth(Rad, pl_trandep)
        derived_rp_diff = diff(derived_rp_gaia, pl_rade)

        is_unphysical_rp_gaia = (
            1 if (derived_rp_gaia is not None and derived_rp_gaia > UNPHYSICAL_RP_THRESHOLD_EARTH_RADII) else 0
        )
        high_ruwe = 1 if (RUWE is not None and RUWE > 1.4) else 0

        return {
            "pl_orbper": raw["pl_orbper"],
            "pl_trandurh": raw["pl_trandurh"],
            "pl_trandep": pl_trandep,
            "pl_rade": pl_rade,
            "pl_insol": raw["pl_insol"],
            "pl_eqt": raw["pl_eqt"],
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
            "derived_rp_gaia": derived_rp_gaia,
            "derived_rp_diff": derived_rp_diff,
            "derived_rp_diff_rel": rel(derived_rp_diff, pl_rade),
            "is_unphysical_rp_gaia": is_unphysical_rp_gaia,
            "RUWE": RUWE,
            "high_ruwe": high_ruwe,
            "j_k": colour(raw["Jmag"], Kmag),
            "h_k": colour(raw["Hmag"], Kmag),
            "abs_K": abs_K,
            "ps_g_r": colour(raw["PS_gmag"], raw["PS_rmag"]),
        }

    def _contributions(self, X_imputed: np.ndarray) -> Tuple[np.ndarray, float]:
        """Per-feature attribution of the positive-class probability, in probability units
        (they sum to p - bias). LightGBM supplies exact TreeSHAP values in log-odds space;
        those are rescaled proportionally so the total shift matches the probability shift
        from the base rate, which keeps the API's existing 'percentage-point' meaning."""
        if hasattr(self.model, "estimators_"):
            return self._rf_contributions(X_imputed)
        raw = self.model.predict(X_imputed, pred_contrib=True)[0]
        phi, base_logit = raw[:-1], float(raw[-1])
        bias = 1.0 / (1.0 + math.exp(-base_logit))
        p = float(self.model.predict_proba(X_imputed)[0][1])
        total = float(phi.sum())
        scale = (p - bias) / total if abs(total) > 1e-12 else 0.0
        return phi * scale, bias

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

    @staticmethod
    def inputs_from_records(candidate_obj, host_obj) -> Dict[str, Any]:
        """DB rows -> the raw-input dict `build_feature_row` expects, using the same source for
        each quantity that training used: `st_*` are the TOI table's (TIC-derived) host values,
        `Teff`/`Rad`/`Dist` the Gaia DR3 ones. Feeding Gaia values into both slots (as an earlier
        version did) made every disagreement feature 0 at serving time. The model is trained on
        TIC/Gaia values, so spectroscopy is never substituted here (it is reported as evidence)."""
        h = host_obj
        return {
            "st_teff": h.toi_teff if h else None,
            "Teff": h.teff if h else None,
            "st_rad": h.toi_rad if h else None,
            "Rad": h.rad if h else None,
            "st_dist": h.toi_dist if h else None,
            "Dist": h.distance if h else None,
            "st_logg": h.toi_logg if h else None,
            "Plx": h.parallax if h else None,
            "Jmag": h.j_mag if h else None,
            "Hmag": h.h_mag if h else None,
            "Kmag": h.k_mag if h else None,
            # HostStar.g_mag/r_mag are Pan-STARRS DR1 bands (not Gaia G) -- matches the
            # PS_gmag/PS_rmag columns the model was trained on.
            "PS_gmag": h.g_mag if h else None,
            "PS_rmag": h.r_mag if h else None,
            "pl_trandep": candidate_obj.trandep,
            "pl_rade": candidate_obj.rade,
            "RUWE": h.ruwe if h else None,
            "pl_orbper": candidate_obj.orbper,
            "pl_trandurh": candidate_obj.trandurh,
            "pl_insol": candidate_obj.insol,
            "pl_eqt": candidate_obj.eqt,
        }

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

            data = self.inputs_from_records(candidate_obj, candidate_obj.host)
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

        contributions, bias = self._contributions(X_imputed)
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
                    model_version=self.model_version,
                )
                db.add(pred_rec)
            else:
                pred_rec.evidence_consistency_score = evidence_score
                pred_rec.followup_priority_score = priority_score
                pred_rec.prob_planet = evidence_score
                pred_rec.feature_importance = top_contrib
                pred_rec.model_version = self.model_version

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
