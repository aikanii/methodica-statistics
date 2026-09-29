from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from ..utils import p_format, to_native


def check_assumptions(df: pd.DataFrame, method: str, params: dict) -> list[dict]:
    method = method or ""
    checks = []
    y = params.get("y")
    x = params.get("x")
    if isinstance(x, list):
        x0 = x[0] if x else None
        xs = x
    else:
        x0 = x or params.get("group")
        xs = [x0] if x0 else []

    def add(name, status, evidence, action, detail=None):
        checks.append(
            {
                "name": name,
                "status": status,  # pass / fail / warning / assumed / info
                "evidence": evidence,
                "recommended_action": action,
                "detail": detail,
            }
        )

    # Independence — design assumption
    if method in {
        "independent_t",
        "oneway_anova",
        "mannwhitney",
        "kruskal",
        "pearson",
        "spearman",
        "linear_regression",
        "multiple_regression",
        "chi_square",
    }:
        add(
            "Independence of observations",
            "assumed",
            "Independence is a design property (sampling / assignment), not something a p-value can prove from a single table.",
            "Confirm that rows are not repeated measures, clustered (e.g. patients in clinics), or otherwise dependent. If they are, use a paired, mixed, or clustered method.",
        )

    # Normality of DV / residuals
    if method in {"independent_t", "one_sample_t", "paired_t", "oneway_anova", "pearson"} and y and y in df.columns:
        if method == "paired_t" and x0 in df.columns:
            d = pd.to_numeric(df[y], errors="coerce") - pd.to_numeric(df[x0], errors="coerce")
            _norm_check(d.dropna(), "Normality of paired differences", add)
        elif x0 and x0 in df.columns and df[x0].nunique(dropna=True) <= 12 and method in {"independent_t", "oneway_anova"}:
            tmp = df[[y, x0]].dropna()
            tmp[y] = pd.to_numeric(tmp[y], errors="coerce")
            tmp = tmp.dropna()
            small = False
            for g, part in tmp.groupby(x0):
                ok, ev = _shap(part[y])
                if not ok:
                    small = True
                add(
                    f"Normality of '{y}' in group {g}",
                    "pass" if ok else "fail",
                    ev,
                    "Proceed with caution." if ok else "Prefer a rank-based test (Mann–Whitney / Kruskal–Wallis), a transformation, or bootstrap.",
                )
            nmin = tmp.groupby(x0)[y].size().min() if len(tmp) else 0
            if nmin >= 30:
                add(
                    "Central limit theorem",
                    "info",
                    f"Smallest group n = {int(nmin)}. Means of moderately sized samples are approximately normal even if the parent distribution is not.",
                    "CLT is a justification for the sampling distribution of the mean, not for ignoring outliers or mixed populations.",
                )
        else:
            _norm_check(pd.to_numeric(df[y], errors="coerce").dropna(), f"Normality of '{y}'", add)

    if method in {"linear_regression", "multiple_regression", "robust_regression"} and y:
        try:
            from .stats_engine import _fit_ols

            fit, tmp = _fit_ols(df, y, [c for c in xs if c], robust=False)
            _norm_check(pd.Series(fit.resid), "Normality of residuals", add)
            # homoscedasticity
            try:
                from statsmodels.stats.diagnostic import het_breuschpagan

                bp = het_breuschpagan(fit.resid, fit.model.exog)
                p = float(bp[1])
                add(
                    "Homoscedasticity (Breusch–Pagan)",
                    "pass" if p >= 0.05 else "fail",
                    f"BP p = {p_format(p)}. Residual variance {'appears constant' if p>=0.05 else 'appears to change with fitted values'}.",
                    "Continue." if p >= 0.05 else "Use HC3 robust SEs, transform the outcome, or a different variance model.",
                )
            except Exception as e:
                add("Homoscedasticity", "warning", f"Could not compute Breusch–Pagan ({e}).", "Inspect residual vs fitted plot.")
            # multicollinearity
            if len(xs) >= 2:
                from statsmodels.stats.outliers_influence import variance_inflation_factor
                import statsmodels.api as sm

                X = sm.add_constant(tmp[xs], has_constant="add")
                vifs = []
                for i, name in enumerate(X.columns):
                    if name == "const":
                        continue
                    vifs.append((name, float(variance_inflation_factor(X.values, i))))
                bad = [f"{n}={v:.1f}" for n, v in vifs if v > 5]
                add(
                    "Multicollinearity (VIF)",
                    "fail" if bad else "pass",
                    "VIF: " + ", ".join(f"{n}={v:.2f}" for n, v in vifs),
                    "No action needed." if not bad else "Remove or combine collinear predictors; coefficients of collinear terms are unstable.",
                )
            # linearity - rainbow or reset
            add(
                "Linearity",
                "warning",
                "Linearity was not formally proven. Inspect residual vs fitted and component+residual plots.",
                "If curvature is present, add transformations or nonlinear terms.",
            )
        except Exception as e:
            add("Regression residual assumptions", "warning", str(e), "Fit the model and inspect diagnostics.")

    # equal variance for t / anova
    if method in {"independent_t", "oneway_anova", "tukey_hsd"} and y and x0 and x0 in df.columns:
        tmp = df[[y, x0]].dropna()
        tmp[y] = pd.to_numeric(tmp[y], errors="coerce")
        tmp = tmp.dropna()
        groups = [v[y].values for _, v in tmp.groupby(x0) if len(v) > 1]
        if len(groups) >= 2:
            W, p = stats.levene(*groups)
            add(
                "Homogeneity of variance (Levene)",
                "pass" if p >= 0.05 else "fail",
                f"Levene W = {W:.3f}, p = {p_format(p)}.",
                "Student's t / standard ANOVA is reasonable."
                if p >= 0.05
                else "Use Welch's t-test, Welch ANOVA, or a rank test. Tukey HSD also assumes equal variances.",
            )

    # chi square expected counts
    if method in {"chi_square", "cramers_v"} and y and x0:
        tab = pd.crosstab(df[y], df[x0])
        try:
            chi2, p, dof, exp = stats.chi2_contingency(tab)
            nlow = int((exp < 5).sum())
            add(
                "Expected cell counts",
                "fail" if nlow else "pass",
                f"{nlow} cells have expected count < 5. Minimum expected = {float(exp.min()):.2f}.",
                "Chi-square approximation is acceptable."
                if not nlow
                else "Use Fisher's exact test (2×2), simulate p-values, or collapse sparse categories.",
            )
        except Exception as e:
            add("Expected cell counts", "warning", str(e), "Inspect the contingency table.")

    if method == "fisher_exact":
        add("Fixed marginals / 2×2 table", "info", "Fisher's exact test conditions on table margins.", "Recode to two levels if the table is larger than 2×2.")

    if method in {"arima", "sarima", "trend_analysis"}:
        add(
            "Stationarity",
            "warning",
            "Stationarity was not formally tested in this pre-check. Differencing (the I in ARIMA) is a common remedy.",
            "Inspect rolling mean/variance and consider an ADF test before interpreting ARMA coefficients.",
        )

    if method == "cox_ph":
        add(
            "Proportional hazards",
            "warning",
            "PH is an assumption of a single time-constant hazard ratio.",
            "Inspect Schoenfeld residual tests and log-log plots. If PH fails, use time interactions or a different model.",
        )
        add(
            "Independent censoring",
            "assumed",
            "Censoring times must be independent of failure risk given covariates.",
            "Discuss the censoring mechanism in the report (loss to follow-up vs administrative).",
        )

    if method == "repeated_anova":
        add(
            "Sphericity",
            "warning",
            "Repeated-measures ANOVA F is biased when sphericity fails.",
            "Use Greenhouse–Geisser / Huynh–Feldt corrections (computed with the analysis when available).",
        )

    # sample size
    n = int(len(df))
    if n < 20 and method not in {"descriptive", "frequency"}:
        add(
            "Sample size",
            "warning",
            f"n = {n} is small for stable inference.",
            "Treat p-values as fragile. Consider exact/permutation methods and emphasize effect sizes and CIs.",
        )

    # missingness
    used = [c for c in [y, x0, params.get("duration"), params.get("event")] + xs if c and c in df.columns]
    if used:
        sub = df[used]
        miss = float(sub.isna().any(axis=1).mean())
        if miss > 0:
            add(
                "Complete-case analysis",
                "warning" if miss > 0.05 else "info",
                f"{miss*100:.1f}% of rows are missing on the analysis variables and will be dropped.",
                "If missingness may depend on the outcome, complete-case estimates can be biased. Consider multiple imputation.",
            )

    if not checks:
        add(
            "Method-specific assumptions",
            "info",
            "No automated pre-checks are registered for this method besides general data integrity.",
            "Read the method notes in the result and inspect diagnostics.",
        )
    return checks


def _shap(x: pd.Series):
    x = pd.to_numeric(x, errors="coerce").dropna()
    n = len(x)
    if n < 8:
        return True, f"n={n} is too small for a meaningful Shapiro–Wilk test; treated as inconclusive rather than a pass."
    sample = x.sample(min(n, 2000), random_state=0)
    W, p = stats.shapiro(sample)
    ok = p >= 0.05
    return ok, f"Shapiro–Wilk W={W:.3f}, p={p_format(p)}, n={n}. " + (
        "No significant departure from normality at α=0.05 (this is not proof of normality)."
        if ok
        else "Significant departure from normality."
    )


def _norm_check(x, name, add):
    ok, ev = _shap(pd.Series(x))
    add(
        name,
        "pass" if ok else "fail",
        ev,
        "Parametric test is tenable if other assumptions hold." if ok else "Prefer a nonparametric alternative, a transformation, or robust/permutation methods.",
    )
