from __future__ import annotations

from ..utils import safe_float


def validate_result(method: str, params: dict, result: dict, assumption_checks: list[dict]) -> dict:
    flags = []
    stats = result.get("statistics") or {}
    p = _find_p(stats)
    n = result.get("n") or stats.get("n")
    es = result.get("effect_size") or {}

    failed = [c for c in assumption_checks if c.get("status") == "fail"]
    if failed and method in {"independent_t", "oneway_anova", "paired_t", "pearson", "linear_regression"}:
        flags.append(
            {
                "level": "warning",
                "code": "assumptions_failed",
                "message": "One or more statistical assumptions were not satisfied. The selected parametric method may not be appropriate.",
                "detail": "; ".join(c["name"] for c in failed),
            }
        )

    if n is not None and safe_float(n, 0) < 20 and method not in {"descriptive", "frequency"}:
        flags.append(
            {
                "level": "warning",
                "code": "small_n",
                "message": "The available sample may be insufficient for reliable inference.",
                "detail": f"n = {n}",
            }
        )

    if p is not None and p < 0.05:
        mag = None
        if isinstance(es, dict):
            mag = es.get("magnitude") or _d_mag(es.get("value") if es.get("name") in {"Cohen's d", "cohens_d"} else None)
            val = safe_float(es.get("value"))
            if val is not None and es.get("name") in {"Cohen's d", "Cohen's d (paired)", "cohens_d"} and abs(val) < 0.3:
                mag = "small"
        if mag == "small" or mag == "negligible":
            flags.append(
                {
                    "level": "warning",
                    "code": "sig_small_effect",
                    "message": "The result is statistically significant, but the effect size is small. Statistical significance should not automatically be interpreted as practical significance.",
                }
            )
        flags.append(
            {
                "level": "info",
                "code": "significance_not_importance",
                "message": "A p-value below α indicates incompatibility with the null under the model; it does not measure importance, probability that H₁ is true, or replicability.",
            }
        )

    if method in {"pearson", "spearman", "kendall", "chi_square"}:
        flags.append(
            {
                "level": "info",
                "code": "not_causation",
                "message": "Association (including correlation) does not establish causation.",
            }
        )

    if method in {"correlation_matrix", "tukey_hsd"} or (method == "chi_square" and False):
        flags.append(
            {
                "level": "warning",
                "code": "multiple_testing",
                "message": "Multiple testing increases the probability of false positives. Consider an appropriate correction.",
            }
        )

    # numerical consistency
    if method == "independent_t":
        t, dfn = stats.get("t"), stats.get("df")
        if t is not None and dfn:
            from scipy import stats as scs

            p2 = float(scs.t.sf(abs(t), dfn) * 2)
            if p is not None and abs(p2 - p) > 1e-4:
                flags.append(
                    {
                        "level": "warning",
                        "code": "inconsistent_p",
                        "message": "Internal cross-check of the t p-value did not match exactly. Inspect degrees of freedom (Welch vs Student).",
                        "detail": f"reported p={p}, recomputed={p2}",
                    }
                )

    if p is not None and (p < 0 or p > 1):
        flags.append({"level": "error", "code": "invalid_p", "message": "p-value is outside [0, 1]. The analysis should not be trusted."})

    ci = stats.get("ci95_low"), stats.get("ci95_high")
    if ci[0] is not None and ci[1] is not None and ci[0] > ci[1]:
        flags.append({"level": "error", "code": "invalid_ci", "message": "Confidence interval bounds are reversed."})

    result_warnings = result.get("warnings") or []
    for w in result_warnings:
        flags.append({"level": "warning", "code": "method_note", "message": w})

    return {
        "ok": not any(f["level"] == "error" for f in flags),
        "flags": flags,
        "p_value": p,
        "n": n,
    }


def _find_p(stats: dict):
    for k in ("p_value", "f_pvalue", "pval"):
        if k in stats and stats[k] is not None:
            return safe_float(stats[k])
    return None


def _d_mag(d):
    if d is None:
        return None
    ad = abs(d)
    if ad < 0.2:
        return "negligible"
    if ad < 0.5:
        return "small"
    if ad < 0.8:
        return "medium"
    return "large"
