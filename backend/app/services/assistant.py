from __future__ import annotations

import re

import pandas as pd

from .profile import profile_dataset
from .quality import assess_quality
from .recommend import recommend
from .stats_engine import run_method
from .types import column_roles
from .validate import validate_result
from .assumptions import check_assumptions


def answer(df: pd.DataFrame, question: str, history: list | None = None) -> dict:
    """Grounded assistant: every numeric claim comes from an actual computation."""
    q = (question or "").strip()
    ql = q.lower()
    roles = column_roles(df)
    citations = []

    def cite(kind, payload):
        citations.append({"kind": kind, "payload": payload})

    if not q:
        return _msg("Ask a question about this dataset. I only report numbers that I compute from your data.", citations)

    if re.search(r"important pattern|what.*(pattern|going on|overview|summary|tell me about)", ql):
        prof = profile_dataset(df)
        qlt = assess_quality(df)
        nums = [c for c, r in roles.items() if r == "numeric"]
        bits = [
            f"The working dataset has {prof['n_rows']} rows and {prof['n_cols']} columns "
            f"({prof['missing_pct']}% missing cells, {prof['duplicate_rows']} duplicate rows). "
            f"Data-quality score: {prof['quality_score']}/100 ({qlt['counts']['high']} high-severity issues)."
        ]
        if nums:
            recs = []
            for c in nums[:5]:
                x = pd.to_numeric(df[c], errors="coerce")
                recs.append(f"{c}: mean={x.mean():.4g}, median={x.median():.4g}, sd={x.std():.4g}, missing={int(x.isna().sum())}")
            bits.append("Numeric snapshot — " + "; ".join(recs) + ".")
        cats = [c for c, r in roles.items() if r in ("categorical", "boolean")]
        if cats:
            bits.append("Categorical variables: " + ", ".join(cats[:8]) + ".")
        bits.append(
            "I will not invent further 'insights'. Ask a specific contrast (e.g. a difference between groups) and I will run a test."
        )
        cite("profile", {"quality_score": prof["quality_score"], "n_rows": prof["n_rows"]})
        return _msg(" ".join(bits), citations)

    if re.search(r"correlat|related|relationship", ql):
        rec = recommend(df, q)
        method = rec["recommended"] if rec["recommended"] in {"pearson", "spearman", "kendall", "chi_square"} else None
        if rec["dependent"] and rec["independent"] and method:
            try:
                res = run_method(df, method, rec["params"])
                cite("analysis", res)
                return _msg(res["interpretation"] + " " + res["summary"], citations, analysis=res, recommendation=rec)
            except Exception as e:
                return _msg(f"I mapped this to {method} but could not compute it: {e}", citations, recommendation=rec)
        # correlation matrix
        try:
            res = run_method(df, "correlation_matrix", {"method": "spearman"})
            cite("analysis", res)
            pairs = res["tables"].get("pairwise") or []
            off = [p for p in pairs if p["x"] != p["y"] and p.get("r") is not None]
            off.sort(key=lambda p: abs(p["r"] or 0), reverse=True)
            top = off[:6]
            lines = [f"{p['x']}–{p['y']}: rₛ={p['r']:.3f}, p={p.get('p')}" for p in top]
            text = (
                "Spearman correlations were computed for all numeric pairs (complete cases). "
                "Strongest absolute associations: " + "; ".join(lines) + ". "
                "These p-values are unadjusted for multiple comparisons. Correlation is not causation."
            )
            return _msg(text, citations, analysis=res)
        except Exception as e:
            return _msg(f"Could not compute a correlation matrix: {e}", citations)

    if re.search(r"which (test|method)|what test should|recommend", ql) or re.search(r"\b(is there|does the|difference|significant)\b", ql):
        rec = recommend(df, q)
        text = (
            f"Recommended analysis: **{rec['recommended_label']}** "
            f"(outcome '{rec.get('dependent')}', predictor/group '{rec.get('independent')}'). "
            "Why: " + " ".join(rec.get("why") or []) + " "
            "You can override this recommendation; I will still check assumptions before interpreting a p-value."
        )
        # If the question is a research question, also run it
        if re.search(r"\b(is there|does|significant|differ|associat|relat)\b", ql):
            try:
                res = run_method(df, rec["recommended"], rec["params"])
                checks = check_assumptions(df, rec["recommended"], rec["params"])
                val = validate_result(rec["recommended"], rec["params"], res, checks)
                cite("analysis", res)
                extra = " ".join(f["message"] for f in val["flags"] if f["level"] in ("warning", "error"))
                text = res["interpretation"] + " " + extra
                return _msg(text, citations, analysis=res, recommendation=rec, assumptions=checks, validation=val)
            except Exception as e:
                return _msg(text + f" I could not execute the test automatically: {e}", citations, recommendation=rec)
        return _msg(text, citations, recommendation=rec)

    if re.search(r"unusual|outlier|anomal", ql):
        qlt = assess_quality(df)
        outs = [i for i in qlt["issues"] if i["kind"] in ("outliers", "extreme_values")]
        if not outs:
            return _msg("No IQR-based outliers were flagged. That does not mean the data are error-free.", citations)
        lines = [f"{i['location']}: {i['problem']}" for i in outs[:12]]
        cite("quality", {"n": len(outs)})
        return _msg(
            "Outliers were flagged with a 1.5×IQR rule (descriptive, not a test of contamination): "
            + " ".join(lines)
            + " Inspect before deleting; many outliers are legitimate.",
            citations,
        )

    if re.search(r"assumpt", ql):
        rec = recommend(df, q if len(q) > 20 else "difference between groups")
        checks = check_assumptions(df, rec["recommended"], rec["params"])
        lines = [f"{c['name']}: {c['status']} — {c['evidence']}" for c in checks]
        return _msg(
            f"Assumption screen for recommended method {rec['recommended_label']}:\n" + "\n".join(lines),
            citations,
            recommendation=rec,
            assumptions=checks,
        )

    if re.search(r"regress|linear model|predict", ql):
        rec = recommend(df, q)
        params = rec["params"]
        if rec["recommended"] not in {"linear_regression", "multiple_regression", "logistic_regression"}:
            nums = [c for c, r in roles.items() if r == "numeric"]
            if len(nums) >= 2:
                params = {"y": rec.get("dependent") or nums[0], "x": [rec.get("independent") or nums[1]]}
            else:
                return _msg("Need at least two numeric columns to fit a regression.", citations)
        try:
            res = run_method(df, "linear_regression", params)
            cite("analysis", res)
            return _msg(res["interpretation"], citations, analysis=res)
        except Exception as e:
            return _msg(f"Regression could not be completed: {e}", citations)

    if re.search(r"missing|quality|clean|duplicate", ql):
        qlt = assess_quality(df)
        cite("quality", qlt["counts"])
        tops = qlt["issues"][:8]
        lines = [f"[{i['severity']}] {i['problem']}" for i in tops]
        return _msg(
            f"Quality score {qlt['score']}/100 with {qlt['counts']['total']} issue(s) "
            f"({qlt['counts']['high']} high). " + " ".join(lines) + " Nothing was changed; cleaning is never silent.",
            citations,
        )

    if re.search(r"explain this result|interpret", ql):
        return _msg(
            "I can interpret a result only if you run an analysis first or ask a concrete research question. "
            "Paste the research question and I will compute the test and explain the numbers I obtained — I will not narrate a p-value I did not calculate.",
            citations,
        )

    # default: treat as research question
    rec = recommend(df, q)
    try:
        res = run_method(df, rec["recommended"], rec["params"])
        checks = check_assumptions(df, rec["recommended"], rec["params"])
        val = validate_result(rec["recommended"], rec["params"], res, checks)
        cite("analysis", {"method": res["method"], "statistics": res["statistics"]})
        return _msg(res["interpretation"], citations, analysis=res, recommendation=rec, assumptions=checks, validation=val)
    except Exception as e:
        return _msg(
            f"I recommended {rec['recommended_label']} for this question but could not run it: {e}. "
            f"Why it was selected: {' '.join(rec.get('why') or [])}",
            citations,
            recommendation=rec,
        )


def _msg(content, citations, **extra):
    return {"role": "assistant", "content": content, "citations": citations, **extra}
