from __future__ import annotations

import re

import numpy as np
import pandas as pd
from scipy import stats

from .types import classify_series, column_roles


DIFF_WORDS = re.compile(
    r"\b(differ|difference|compare|comparison|versus|vs\.?|between|higher|lower|greater|less|affect|effect|impact|improve|change|than)\b",
    re.I,
)
REL_WORDS = re.compile(
    r"\b(relat|associat|correlat|predict|influence|linked|connection|linear|regression|depend)\b",
    re.I,
)
TREND_WORDS = re.compile(r"\b(trend|over time|forecast|season|time series|temporal|growth)\b", re.I)
SURV_WORDS = re.compile(r"\b(surviv|hazard|time to|kaplan|censor|death|event-free)\b", re.I)
CLUSTER_WORDS = re.compile(r"\b(cluster|segment|group similar|latent|factor analysis|pca|dimension)\b", re.I)
PAIRED_WORDS = re.compile(r"\b(paired|before|after|pre[- ]?post|repeated|within subject|matched)\b", re.I)


def _match_columns(question: str, columns: list[str]) -> list[str]:
    q = question.lower()
    found = []
    # longest names first to avoid partial overlaps
    for c in sorted(columns, key=lambda x: len(str(x)), reverse=True):
        name = str(c)
        variants = {
            name.lower(),
            name.lower().replace("_", " "),
            name.lower().replace("-", " "),
            re.sub(r"[^a-z0-9]+", "", name.lower()),
        }
        # common aliases
        compact = re.sub(r"[^a-z0-9]", "", name.lower())
        variants.add(compact)
        if compact == "pm25":
            variants.update(["pm2.5", "pm 2.5", "pm2.5"])
        for v in variants:
            if v and v in q:
                found.append(name)
                break
    # unique preserve order
    out = []
    for c in found:
        if c not in out:
            out.append(c)
    return out


def _normalish(x: pd.Series) -> tuple[bool, dict]:
    x = pd.to_numeric(x, errors="coerce").dropna()
    n = len(x)
    if n < 8:
        return True, {"note": "n too small for a powerful normality test; treating as approximate.", "n": n}
    sample = x.sample(min(n, 2000), random_state=0)
    try:
        if len(sample) <= 5000:
            W, p = stats.shapiro(sample)
            return bool(p >= 0.05 or n >= 200), {"test": "shapiro", "W": float(W), "p": float(p), "n": n}
    except Exception:
        pass
    # fallback skew
    sk = float(sample.skew())
    return abs(sk) < 1.0, {"test": "skewness", "skew": sk, "n": n}


def recommend(df: pd.DataFrame, question: str, hint: dict | None = None) -> dict:
    hint = hint or {}
    roles = column_roles(df)
    cols = list(df.columns)
    mentioned = _match_columns(question, cols)
    q = question or ""

    intent = "explore"
    if SURV_WORDS.search(q):
        intent = "survival"
    elif TREND_WORDS.search(q):
        intent = "trend"
    elif CLUSTER_WORDS.search(q):
        intent = "structure"
    elif REL_WORDS.search(q):
        intent = "relationship"
    elif DIFF_WORDS.search(q):
        intent = "difference"
    elif mentioned and len(mentioned) >= 2:
        intent = "relationship"

    # user overrides
    y = hint.get("y")
    x = hint.get("x")
    paired = bool(hint.get("paired") or PAIRED_WORDS.search(q))

    if not y or not x:
        # pick from mentioned
        nums = [c for c in mentioned if roles.get(c) == "numeric"]
        cats = [c for c in mentioned if roles.get(c) in ("categorical", "boolean")]
        dts = [c for c in mentioned if roles.get(c) == "datetime"]
        if intent == "difference":
            y = y or (nums[0] if nums else None)
            x = x or (cats[0] if cats else (nums[1] if len(nums) > 1 else None))
        elif intent == "relationship":
            if len(nums) >= 2:
                y, x = y or nums[0], x or nums[1]
            elif nums and cats:
                y, x = y or nums[0], x or cats[0]
            elif len(cats) >= 2:
                y, x = y or cats[0], x or cats[1]
        elif intent == "trend":
            y = y or (nums[0] if nums else None)
            x = x or (dts[0] if dts else None)
        else:
            if nums:
                y = y or nums[0]
            if cats:
                x = x or cats[0]
            elif len(nums) > 1:
                x = x or nums[1]

    # fallback: first numeric + first categorical
    if not y:
        nums_all = [c for c, r in roles.items() if r == "numeric"]
        y = nums_all[0] if nums_all else (cols[0] if cols else None)
    if not x:
        cats_all = [c for c, r in roles.items() if r in ("categorical", "boolean") and c != y]
        nums_all = [c for c, r in roles.items() if r == "numeric" and c != y]
        x = cats_all[0] if cats_all else (nums_all[0] if nums_all else None)

    rec = _decide(df, roles, intent, y, x, paired, question)
    rec["research_question"] = question
    rec["intent"] = intent
    rec["mentioned_columns"] = mentioned
    rec["roles"] = {k: roles[k] for k in mentioned if k in roles}
    return rec


def _decide(df, roles, intent, y, x, paired, question) -> dict:
    why = []
    assumptions = []
    alternatives = []
    method = "descriptive"
    params = {}
    warnings = []

    y_role = roles.get(y)
    x_role = roles.get(x)

    if intent == "survival":
        # guess duration/event
        dur = y if y_role == "numeric" else None
        event = None
        for c, r in roles.items():
            if r in ("boolean", "numeric") and re.search(r"event|status|censor|died|death", str(c), re.I):
                event = c
                break
        method = "kaplan_meier" if not x_role or x_role not in ("categorical", "boolean") else "logrank"
        params = {"duration": dur, "event": event, "group": x if x_role in ("categorical", "boolean") else None}
        why.append("The question involves time-to-event / survival outcomes.")
        return _pack(method, params, y, x, why, assumptions, alternatives, warnings)

    if intent == "trend" and y_role == "numeric":
        method, params = "trend_analysis", {"y": y, "time": x if x_role == "datetime" else None}
        why.append("The question is about change over time in a numeric series.")
        alternatives = [
            {"method": "arima", "when": "If you need a formal forecast with ARMA errors."},
            {"method": "seasonality", "when": "If a repeating cycle is expected."},
        ]
        return _pack(method, params, y, x, why, assumptions, alternatives, warnings)

    if intent == "structure":
        nums = [c for c, r in roles.items() if r == "numeric"]
        method, params = "pca", {"columns": nums}
        why.append("The question asks about latent structure or grouping among variables.")
        alternatives = [{"method": "kmeans", "when": "If the goal is to segment observations rather than variables."}]
        return _pack(method, params, y, x, why, assumptions, alternatives, warnings)

    # two categoricals
    if y_role in ("categorical", "boolean") and x_role in ("categorical", "boolean"):
        tab = pd.crosstab(df[y], df[x])
        if tab.shape == (2, 2):
            expected_ok = True
            try:
                from scipy import stats as scs

                chi2, p, dof, exp = scs.chi2_contingency(tab)
                expected_ok = (exp >= 5).all()
            except Exception:
                expected_ok = False
            if expected_ok:
                method, params = "chi_square", {"x": x, "y": y}
                why += ["Both variables are categorical.", "The contingency table is 2×2 with adequate expected counts."]
                alternatives = [{"method": "fisher_exact", "when": "If any expected cell count is < 5."}]
            else:
                method, params = "fisher_exact", {"x": x, "y": y}
                why += ["Both variables are categorical.", "A 2×2 table with small expected counts favors Fisher's exact test."]
        else:
            method, params = "chi_square", {"x": x, "y": y}
            why += ["Both variables are categorical.", "Chi-square tests independence in the contingency table."]
            alternatives = [{"method": "cramers_v", "when": "To quantify association strength after the test."}]
        return _pack(method, params, y, x, why, assumptions, alternatives, warnings)

    # numeric vs categorical
    if y_role == "numeric" and x_role in ("categorical", "boolean"):
        raw_levels = df[x].dropna().astype(str)
        levels_norm = raw_levels.str.strip().str.title()
        levels = int(levels_norm.nunique())
        mentioned_lv = []
        qlow = (question or "").lower()
        for lv in sorted(levels_norm.unique(), key=lambda z: -len(str(z))):
            if str(lv).lower() in qlow:
                mentioned_lv.append(str(lv))
        tmp = df[[y, x]].dropna().copy()
        tmp[y] = pd.to_numeric(tmp[y], errors="coerce")
        tmp = tmp.dropna()
        tmp["_g"] = tmp[x].astype(str).str.strip().str.title()
        if len(mentioned_lv) >= 2:
            tmp = tmp[tmp["_g"].isin(mentioned_lv[:2])]
            levels = 2
            why.append(f"The question names two groups ({mentioned_lv[0]} vs {mentioned_lv[1]}); analysis is restricted to those levels.")
        groups = [v[y] for _, v in tmp.groupby("_g")]
        n_per = [len(g) for g in groups]
        why.append(f"Dependent variable '{y}' is numeric.")
        why.append(f"Independent variable '{x}' has {levels} group(s) after standardizing labels.")
        params = {"y": y, "x": x}
        if len(mentioned_lv) >= 2:
            params["levels"] = mentioned_lv[:2]
        if int(raw_levels.nunique()) != levels:
            warnings.append(
                f"'{x}' has inconsistent labels (whitespace/case). Standardize categories in Cleaning before treating group counts as final."
            )

        if paired and levels == 2:
            method = "paired_t"
            why.append("The question suggests paired / before–after measurements.")
            alternatives = [{"method": "wilcoxon", "when": "If the paired differences are clearly non-normal."}]
            return _pack(method, {"y": y, "x": x}, y, x, why, assumptions, alternatives, warnings)

        if levels <= 1:
            method = "descriptive"
            warnings.append("The grouping variable has fewer than 2 levels in the current data.")
            return _pack(method, {"columns": [y]}, y, x, why, assumptions, alternatives, warnings)

        # normality / variance
        normal_flags = []
        for g in groups:
            ok, ev = _normalish(g)
            normal_flags.append(ok)
        approx_normal = all(normal_flags) or min(n_per) >= 30
        if min(n_per) >= 30:
            why.append("Group sizes are ≥ 30, so the sampling distribution of the mean is approximately normal by CLT.")
        elif approx_normal:
            why.append("Group distributions are approximately consistent with normality.")
        else:
            why.append("At least one group appears non-normal and n is modest.")

        if levels == 2:
            if approx_normal:
                method = "independent_t"
                alternatives = [{"method": "mannwhitney", "when": "If normality or equal-shape assumptions are doubtful."}]
                assumptions = [
                    {"name": "Independence", "status": "assumed", "note": "Observations in different groups are treated as independent. Verify the sampling design."},
                    {"name": "Approximate normality", "status": "checked", "note": "Shapiro–Wilk / skewness screened per group (or CLT invoked)."},
                    {"name": "Homogeneity of variance", "status": "checked_at_run", "note": "Levene's test is run with the t-test; Welch's correction is applied if violated."},
                ]
            else:
                method = "mannwhitney"
                why.append("Nonparametric Mann–Whitney U is preferred when parametric assumptions are not tenable.")
                alternatives = [{"method": "independent_t", "when": "If you have a strong reason to treat the means as normal (e.g. large n)."}]
        else:
            if approx_normal:
                method = "oneway_anova"
                alternatives = [
                    {"method": "kruskal", "when": "If normality or equal-variance assumptions fail."},
                    {"method": "tukey_hsd", "when": "For pairwise follow-up after a significant ANOVA."},
                ]
                assumptions = [
                    {"name": "Independence", "status": "assumed", "note": "Subjects are independent across groups."},
                    {"name": "Approximate normality", "status": "checked", "note": "Screened per group."},
                    {"name": "Homogeneity of variance", "status": "checked_at_run", "note": "Levene's test accompanies ANOVA."},
                ]
            else:
                method = "kruskal"
                why.append("Kruskal–Wallis is the rank-based analogue of one-way ANOVA.")
                alternatives = [{"method": "oneway_anova", "when": "If residuals are acceptably normal and variances are similar."}]
        return _pack(method, params, y, x, why, assumptions, alternatives, warnings)

    # two numerics
    if y_role == "numeric" and x_role == "numeric":
        why.append(f"Both '{y}' and '{x}' are numeric.")
        if intent == "difference" and paired:
            method, params = "paired_t", {"y": y, "x": x}
            why.append("Two numeric columns with a paired framing → paired t-test on row-aligned differences.")
            alternatives = [{"method": "wilcoxon", "when": "If differences are skewed."}]
            return _pack(method, params, y, x, why, assumptions, alternatives, warnings)
        # relationship
        a = pd.to_numeric(df[x], errors="coerce")
        b = pd.to_numeric(df[y], errors="coerce")
        m = a.notna() & b.notna()
        ok_y, evy = _normalish(b[m])
        ok_x, evx = _normalish(a[m])
        if intent in ("relationship", "explore") and re.search(r"predict|regress|model", question or "", re.I):
            method, params = "linear_regression", {"y": y, "x": [x]}
            why.append("The question asks to predict or model one numeric variable from another.")
            alternatives = [{"method": "spearman", "when": "If you only need a rank association, not a fitted line."}]
        elif ok_x and ok_y:
            method, params = "pearson", {"x": x, "y": y}
            why.append("Pearson r measures linear association under approximate bivariate normality.")
            alternatives = [
                {"method": "spearman", "when": "If the relationship is monotonic but not linear, or outliers are influential."},
                {"method": "linear_regression", "when": "If you need a slope, intercept, and residual diagnostics."},
            ]
        else:
            method, params = "spearman", {"x": x, "y": y}
            why.append("Distributions appear non-normal; Spearman rank correlation is more robust.")
            alternatives = [{"method": "pearson", "when": "If a linear Pearson coefficient is specifically required and n is large."}]
        return _pack(method, params, y, x, why, assumptions, alternatives, warnings)

    # fallback
    method, params = "descriptive", {"columns": [c for c, r in roles.items() if r == "numeric"][:8]}
    why.append("Could not confidently map the question onto a specific test; starting with descriptives.")
    warnings.append("Specify the outcome and grouping/predictor variables if this recommendation looks wrong.")
    return _pack(method, params, y, x, why, assumptions, alternatives, warnings)


def _pack(method, params, y, x, why, assumptions, alternatives, warnings):
    labels = {
        "independent_t": "Independent-samples t-test",
        "paired_t": "Paired t-test",
        "mannwhitney": "Mann–Whitney U test",
        "oneway_anova": "One-way ANOVA",
        "kruskal": "Kruskal–Wallis test",
        "pearson": "Pearson correlation",
        "spearman": "Spearman rank correlation",
        "chi_square": "Chi-square test of independence",
        "fisher_exact": "Fisher's exact test",
        "linear_regression": "Simple linear regression",
        "wilcoxon": "Wilcoxon signed-rank test",
        "kaplan_meier": "Kaplan–Meier survival",
        "logrank": "Log-rank test",
        "trend_analysis": "Linear trend analysis",
        "pca": "Principal component analysis",
        "descriptive": "Descriptive statistics",
    }
    return {
        "recommended": method,
        "recommended_label": labels.get(method, method),
        "params": params,
        "dependent": y,
        "independent": x,
        "why": why,
        "assumptions": assumptions
        or [
            {"name": "See assumption engine", "status": "pending", "note": "Full assumption checks run immediately before analysis."}
        ],
        "alternatives": alternatives,
        "warnings": warnings,
        "override_allowed": True,
    }
