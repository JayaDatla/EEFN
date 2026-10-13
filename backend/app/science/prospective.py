"""
Pure evaluation logic for the pre-registered prospective test (docs/prospective_evaluation.md).

Question: among TOIs that were UNRESOLVED (disposition PC) when a snapshot was frozen, are the ones
that carried a catalog-hygiene flag more likely to be later dispositioned as false positives (FP/FA)
than the ones that carried none? That is the claim "flagging saves follow-up effort" would need.

Everything here is a function of (snapshot rows, later dispositions) -- no network, no database -- so
it can be tested exactly and cannot be tuned after seeing outcomes.
"""
import math
from typing import Dict, List, Optional

PLANET = {"CP", "KP"}
FALSE_POSITIVE = {"FP", "FA"}

# Pre-registered guard: no conclusion is drawn until enough candidates have resolved.
MIN_RESOLVED = 60
MIN_PER_ARM = 10


def wilson_interval(k: int, n: int, z: float = 1.96) -> Optional[List[float]]:
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [max(0.0, centre - half), min(1.0, centre + half)]


def risk_difference_ci(k1: int, n1: int, k0: int, n0: int, z: float = 1.96) -> Optional[List[float]]:
    """Newcombe's hybrid-score interval for p1 - p0 (flagged minus unflagged FP rate)."""
    if n1 == 0 or n0 == 0:
        return None
    l1, u1 = wilson_interval(k1, n1, z)
    l0, u0 = wilson_interval(k0, n0, z)
    p1, p0 = k1 / n1, k0 / n0
    lo = (p1 - p0) - math.sqrt((p1 - l1) ** 2 + (u0 - p0) ** 2)
    hi = (p1 - p0) + math.sqrt((u1 - p1) ** 2 + (p0 - l0) ** 2)
    return [lo, hi]


def fisher_exact_one_sided(k1: int, n1: int, k0: int, n0: int) -> Optional[float]:
    """P(flagged group has >= k1 false positives | margins fixed); H1: flagged FP rate is higher."""
    if n1 == 0 or n0 == 0:
        return None
    from scipy.stats import fisher_exact
    return float(fisher_exact([[k1, n1 - k1], [k0, n0 - k0]], alternative="greater")[1])


def classify(disposition: Optional[str]) -> Optional[str]:
    if disposition in PLANET:
        return "planet"
    if disposition in FALSE_POSITIVE:
        return "false_positive"
    return None      # still PC/APC, or withdrawn: not an outcome


def evaluate(rows: List[dict], dispositions: Dict[str, Optional[str]], flag_names: List[str]) -> dict:
    """`rows`: snapshot rows ({"toi": "104.01", "flags": {...}, "any_core_flag": bool|None, ...}).
    `dispositions`: current TFOP disposition keyed by the same TOI string (missing = withdrawn)."""
    outcomes = []
    pending = withdrawn = 0
    for r in rows:
        if r["toi"] not in dispositions:
            withdrawn += 1
            continue
        c = classify(dispositions[r["toi"]])
        if c is None:
            pending += 1
            continue
        outcomes.append((r, c))

    n_resolved = len(outcomes)
    out = {"n_in_snapshot": len(rows), "n_resolved": n_resolved, "n_still_unresolved": pending,
           "n_withdrawn_excluded": withdrawn,
           "base_rate_false_positive": (sum(1 for _, c in outcomes if c == "false_positive") / n_resolved) if n_resolved else None,
           "per_flag": {}}

    for name in ["any_core_flag"] + flag_names:
        def val(r):
            return r["any_core_flag"] if name == "any_core_flag" else r["flags"].get(name)
        flagged = [c for r, c in outcomes if val(r) is True]
        clean = [c for r, c in outcomes if val(r) is False]
        k1, n1 = sum(1 for c in flagged if c == "false_positive"), len(flagged)
        k0, n0 = sum(1 for c in clean if c == "false_positive"), len(clean)
        all_fp = sum(1 for _, c in outcomes if c == "false_positive")
        out["per_flag"][name] = {
            "n_flagged": n1, "fp_among_flagged": k1,
            "fp_rate_flagged": (k1 / n1) if n1 else None, "fp_rate_flagged_ci95": wilson_interval(k1, n1),
            "n_clean": n0, "fp_among_clean": k0,
            "fp_rate_clean": (k0 / n0) if n0 else None, "fp_rate_clean_ci95": wilson_interval(k0, n0),
            "risk_difference": ((k1 / n1) - (k0 / n0)) if n1 and n0 else None,
            "risk_difference_ci95": risk_difference_ci(k1, n1, k0, n0),
            "p_value_one_sided_fisher": fisher_exact_one_sided(k1, n1, k0, n0),
            "share_of_all_false_positives_flagged": (k1 / all_fp) if all_fp else None,
            "n_not_checkable": sum(1 for r, _ in outcomes if val(r) is None),
        }

    p = out["per_flag"]["any_core_flag"]
    enough = n_resolved >= MIN_RESOLVED and p["n_flagged"] >= MIN_PER_ARM and p["n_clean"] >= MIN_PER_ARM
    out["conclusion_allowed"] = bool(enough)
    if not enough:
        out["verdict"] = (f"TOO EARLY: {n_resolved} of {len(rows)} candidates have resolved "
                          f"(need >= {MIN_RESOLVED} resolved and >= {MIN_PER_ARM} in each arm). No conclusion is drawn.")
    else:
        rd, ci, pv = p["risk_difference"], p["risk_difference_ci95"], p["p_value_one_sided_fisher"]
        if ci[0] > 0 and pv < 0.05:
            out["verdict"] = (f"SUPPORTED: candidates with a core catalog flag were {rd:+.2f} more likely to resolve as "
                              f"false positives (95% CI {ci[0]:+.2f} to {ci[1]:+.2f}, one-sided Fisher p={pv:.3f}).")
        else:
            out["verdict"] = (f"NOT SUPPORTED: risk difference {rd:+.2f} (95% CI {ci[0]:+.2f} to {ci[1]:+.2f}, "
                              f"one-sided Fisher p={pv:.3f}); the flags did not separate later false positives from the rest.")
    return out
