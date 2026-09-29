from __future__ import annotations

import warnings
from typing import Any, Callable

import numpy as np
import pandas as pd
from scipy import stats

from ..utils import p_format, safe_float, sig_label, to_native
from .types import classify_series

warnings.filterwarnings("ignore")


def _series(df, col) -> pd.Series:
    if col not in df.columns:
        raise ValueError(f"Column '{col}' was not found in the dataset.")
    return df[col]


def _num(df, col) -> pd.Series:
    s = pd.to_numeric(_series(df, col), errors="coerce").dropna()
    if s.empty:
        raise ValueError(f"'{col}' has no numeric values after cleaning.")
    return s


def _groups(df, y, g, levels=None) -> dict[str, pd.Series]:
    tmp = df[[y, g]].dropna().copy()
    tmp[y] = pd.to_numeric(tmp[y], errors="coerce")
    tmp = tmp.dropna()
    tmp["_g"] = tmp[g].astype(str).str.strip().str.title()
    if levels:
        want = {str(x).strip().title() for x in levels}
        tmp = tmp[tmp["_g"].isin(want)]
    if tmp.empty:
        raise ValueError("No complete cases for the selected variables.")
    out = {str(k): v[y] for k, v in tmp.groupby("_g")}
    return out


def _ci_mean(x: pd.Series, alpha=0.05):
    n = len(x)
    m = float(x.mean())
    se = float(x.std(ddof=1) / np.sqrt(n)) if n > 1 else 0
    tcrit = float(stats.t.ppf(1 - alpha / 2, n - 1)) if n > 1 else 0
    return m - tcrit * se, m + tcrit * se, se


def _cohens_d(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    na, nb = len(a), len(b)
    va, vb = a.var(ddof=1), b.var(ddof=1)
    sp = np.sqrt(((na - 1) * va + (nb - 1) * vb) / max(na + nb - 2, 1))
    if sp == 0:
        return 0.0
    return float((a.mean() - b.mean()) / sp)


def _hedges_g(d, n):
    if n <= 2:
        return d
    return float(d * (1 - 3 / (4 * n - 9)))


def result(method, label, summary, statistics, interpretation, **kw):
    out = {
        "method": method,
        "method_label": label,
        "summary": summary,
        "statistics": to_native(statistics),
        "interpretation": interpretation,
        "tables": to_native(kw.get("tables") or {}),
        "warnings": kw.get("warnings") or [],
        "notes": kw.get("notes") or [],
        "formula": kw.get("formula"),
        "n": kw.get("n"),
        "effect_size": to_native(kw.get("effect_size")),
        "confidence_intervals": to_native(kw.get("confidence_intervals")),
        "model_diagnostics": to_native(kw.get("model_diagnostics")),
        "pairs": to_native(kw.get("pairs")),
        "inspect": to_native(kw.get("inspect") or statistics),
    }
    return out


# ── Descriptive ──────────────────────────────────────────────


def descriptive(df, params):
    cols = params.get("columns") or [
        c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])
    ]
    rows = []
    for c in cols:
        if c not in df.columns:
            continue
        x = pd.to_numeric(df[c], errors="coerce").dropna()
        if x.empty:
            continue
        lo, hi, se = _ci_mean(x)
        mode = x.mode()
        rows.append(
            {
                "variable": c,
                "n": int(len(x)),
                "mean": float(x.mean()),
                "median": float(x.median()),
                "mode": float(mode.iloc[0]) if len(mode) else None,
                "std": float(x.std(ddof=1)) if len(x) > 1 else 0,
                "variance": float(x.var(ddof=1)) if len(x) > 1 else 0,
                "min": float(x.min()),
                "max": float(x.max()),
                "range": float(x.max() - x.min()),
                "q1": float(x.quantile(0.25)),
                "q3": float(x.quantile(0.75)),
                "iqr": float(x.quantile(0.75) - x.quantile(0.25)),
                "p05": float(x.quantile(0.05)),
                "p95": float(x.quantile(0.95)),
                "skewness": float(x.skew()),
                "kurtosis": float(x.kurtosis()),
                "se": se,
                "ci95_low": lo,
                "ci95_high": hi,
            }
        )
    return result(
        "descriptive",
        "Descriptive statistics",
        f"Descriptive statistics for {len(rows)} numeric variable(s).",
        {"n_variables": len(rows)},
        "These summaries describe the sample; they are not inferential claims about a population.",
        tables={"descriptives": rows},
        n=int(len(df)),
    )


def frequency(df, params):
    col = params.get("column") or params.get("x")
    s = _series(df, col).dropna()
    vc = s.astype(str).value_counts()
    n = int(vc.sum())
    table = [
        {"level": str(i), "count": int(c), "percent": round(100 * c / n, 2), "cum_percent": None}
        for i, c in vc.items()
    ]
    cum = 0
    for r in table:
        cum += r["percent"]
        r["cum_percent"] = round(cum, 2)
    return result(
        "frequency",
        "Frequency table",
        f"Frequency distribution of '{col}' ({len(table)} levels, n={n}).",
        {"n": n, "n_levels": len(table)},
        "Percentages are of non-missing observations.",
        tables={"frequencies": table},
        n=n,
    )


# ── Normality ────────────────────────────────────────────────


def shapiro_wilk(df, params):
    x = _num(df, params.get("column") or params.get("y"))
    if len(x) > 5000:
        x = x.sample(5000, random_state=0)
        note = "Shapiro–Wilk was computed on a random subsample of 5,000 (the test is overly sensitive in very large samples)."
    else:
        note = "Shapiro–Wilk is most appropriate for n ≤ 5000. A non-significant result does not prove normality."
    if len(x) < 3:
        raise ValueError("Shapiro–Wilk requires at least 3 observations.")
    W, p = stats.shapiro(x)
    return result(
        "shapiro_wilk",
        "Shapiro–Wilk normality test",
        f"W = {W:.4f}, p = {p_format(p)} — {sig_label(p)} departure from normality.",
        {"W": float(W), "p_value": float(p), "n": int(len(x))},
        (
            f"The Shapiro–Wilk test evaluates whether the sample is consistent with a normal distribution. "
            f"W={W:.4f}, p={p_format(p)}. "
            + (
                "The data significantly deviate from normality. Prefer nonparametric methods or transformations."
                if p < 0.05
                else "No significant evidence against normality at α=0.05. This is not proof of normality; also inspect Q–Q plots."
            )
        ),
        notes=[note],
        n=int(len(x)),
        formula="W = (∑ a_i x_(i))² / ∑ (x_i − x̄)²",
    )


def anderson_darling(df, params):
    x = _num(df, params.get("column") or params.get("y"))
    r = stats.anderson(x, dist="norm")
    # 5% critical is typically index 2
    crit5 = float(r.critical_values[2]) if len(r.critical_values) > 2 else None
    reject = bool(r.statistic > crit5) if crit5 is not None else None
    return result(
        "anderson_darling",
        "Anderson–Darling normality test",
        f"A² = {r.statistic:.4f}; 5% critical value = {crit5}. "
        + ("Rejects normality." if reject else "Does not reject normality at 5%."),
        {
            "A2": float(r.statistic),
            "critical_values": {str(sl): float(cv) for sl, cv in zip(r.significance_level, r.critical_values)},
            "reject_at_5pct": reject,
            "n": int(len(x)),
        },
        "Anderson–Darling places more weight on the tails than Kolmogorov–Smirnov. Compare A² with the tabulated critical values.",
        n=int(len(x)),
    )


def ks_normal(df, params):
    x = _num(df, params.get("column") or params.get("y"))
    z = (x - x.mean()) / x.std(ddof=1)
    D, p = stats.kstest(z, "norm")
    return result(
        "kolmogorov_smirnov",
        "Kolmogorov–Smirnov test (normal)",
        f"D = {D:.4f}, p = {p_format(p)} — {sig_label(p)} vs. fitted normal.",
        {"D": float(D), "p_value": float(p), "n": int(len(x))},
        "KS is applied to standardized data versus N(0,1). Parameters were estimated from the sample, so p-values are approximate (Lilliefors issue).",
        n=int(len(x)),
        warnings=["Parameters estimated from data: KS p-value is anti-conservative. Prefer Shapiro–Wilk or Anderson–Darling."],
    )


# ── Correlation ──────────────────────────────────────────────


def _corr_pair(df, params, method):
    xcol = params.get("x")
    ycol = params.get("y")
    a = pd.to_numeric(df[xcol], errors="coerce")
    b = pd.to_numeric(df[ycol], errors="coerce")
    mask = a.notna() & b.notna()
    a, b = a[mask], b[mask]
    n = int(len(a))
    if n < 4:
        raise ValueError("Correlation requires at least 4 paired observations.")
    if method == "pearson":
        r, p = stats.pearsonr(a, b)
        # Fisher CI
        z = np.arctanh(np.clip(r, -0.999999, 0.999999))
        se = 1 / np.sqrt(n - 3)
        lo, hi = np.tanh(z - 1.96 * se), np.tanh(z + 1.96 * se)
        label = "Pearson correlation"
        formula = "r = Σ (x−x̄)(y−ȳ) / √[Σ(x−x̄)² Σ(y−ȳ)²]"
        interp_kind = "linear association"
    elif method == "spearman":
        r, p = stats.spearmanr(a, b)
        z = np.arctanh(np.clip(r, -0.999999, 0.999999))
        se = 1 / np.sqrt(n - 3)
        lo, hi = np.tanh(z - 1.96 * se), np.tanh(z + 1.96 * se)
        label = "Spearman rank correlation"
        formula = "ρ = 1 − 6 Σ d_i² / (n(n²−1))"
        interp_kind = "monotonic association"
    else:
        r, p = stats.kendalltau(a, b)
        lo = hi = None
        label = "Kendall's tau"
        formula = "τ = (C − D) / √[(C+D+T_x)(C+D+T_y)]"
        interp_kind = "ordinal association"
    mag = abs(r)
    strength = "negligible" if mag < 0.1 else "weak" if mag < 0.3 else "moderate" if mag < 0.5 else "strong"
    direction = "positive" if r > 0 else "negative" if r < 0 else "null"
    return result(
        method,
        label,
        f"{label.split()[0]} = {r:.3f}, p = {p_format(p)}, n = {n}. {strength.title()} {direction} {interp_kind}.",
        {
            "coefficient": float(r),
            "p_value": float(p),
            "n": n,
            "ci95_low": float(lo) if lo is not None else None,
            "ci95_high": float(hi) if hi is not None else None,
        },
        (
            f"There is a {strength} {direction} {interp_kind} between '{xcol}' and '{ycol}' "
            f"(coefficient={r:.3f}, 95% CI [{lo:.3f}, {hi:.3f}] n={n}). "
            f"The association is {sig_label(p)}. "
            "Correlation does not establish causation; confounding, reverse causation, and coincidence remain possible."
            if lo is not None
            else (
                f"There is a {strength} {direction} {interp_kind} between '{xcol}' and '{ycol}' "
                f"(coefficient={r:.3f}, n={n}). {sig_label(p).capitalize()}. Correlation is not causation."
            )
        ),
        n=n,
        effect_size={"name": method, "value": float(r), "magnitude": strength},
        confidence_intervals={"coefficient": [lo, hi]} if lo is not None else None,
        formula=formula,
        warnings=["Correlation indicates association and does not establish causation."],
        pairs={"x": xcol, "y": ycol},
    )


def pearson(df, params):
    return _corr_pair(df, params, "pearson")


def spearman(df, params):
    return _corr_pair(df, params, "spearman")


def kendall(df, params):
    return _corr_pair(df, params, "kendall")


def correlation_matrix(df, params):
    cols = params.get("columns") or [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    method = params.get("method", "pearson")
    sub = df[cols].apply(pd.to_numeric, errors="coerce")
    corr = sub.corr(method=method)
    pmat = pd.DataFrame(np.nan, index=cols, columns=cols)
    nmat = pd.DataFrame(0, index=cols, columns=cols)
    for i, a in enumerate(cols):
        for b in cols[i:]:
            x, y = sub[a], sub[b]
            m = x.notna() & y.notna()
            nmat.loc[a, b] = nmat.loc[b, a] = int(m.sum())
            if m.sum() > 3:
                if method == "pearson":
                    r, p = stats.pearsonr(x[m], y[m])
                elif method == "spearman":
                    r, p = stats.spearmanr(x[m], y[m])
                else:
                    r, p = stats.kendalltau(x[m], y[m])
                pmat.loc[a, b] = pmat.loc[b, a] = p
    records = []
    for a in cols:
        for b in cols:
            records.append(
                {
                    "x": a,
                    "y": b,
                    "r": to_native(corr.loc[a, b]),
                    "p": to_native(pmat.loc[a, b]),
                    "n": int(nmat.loc[a, b]),
                }
            )
    return result(
        "correlation_matrix",
        f"{method.title()} correlation matrix",
        f"{method.title()} correlations among {len(cols)} variables.",
        {"method": method, "n_vars": len(cols)},
        "Each cell is a pairwise complete-case correlation. p-values are unadjusted for multiple comparisons.",
        tables={"pairwise": records, "matrix": to_native(corr.reset_index().rename(columns={"index": "variable"}))},
        warnings=["Multiple pairwise tests inflate the false-positive rate. Consider a correction if screening many pairs."],
        n=int(len(sub.dropna())),
    )


# ── Association ──────────────────────────────────────────────


def chi_square(df, params):
    a, b = params.get("x"), params.get("y")
    tab = pd.crosstab(df[a], df[b])
    if tab.shape[0] < 2 or tab.shape[1] < 2:
        raise ValueError("Chi-square requires at least a 2×2 table.")
    chi2, p, dof, expected = stats.chi2_contingency(tab)
    n = int(tab.values.sum())
    # Cramer's V
    r, c = tab.shape
    v = float(np.sqrt(chi2 / (n * (min(r, c) - 1)))) if n and min(r, c) > 1 else 0
    low_exp = int((expected < 5).sum())
    warns = []
    if low_exp:
        warns.append(
            f"{low_exp} expected cell count(s) are < 5. Chi-square approximation may be poor; consider Fisher's exact test (2×2) or collapsing categories."
        )
    mag = "negligible" if v < 0.1 else "small" if v < 0.3 else "medium" if v < 0.5 else "large"
    table = tab.reset_index()
    table.columns = [str(c) for c in table.columns]
    exp_df = pd.DataFrame(expected, index=tab.index, columns=tab.columns).reset_index()
    return result(
        "chi_square",
        "Chi-square test of independence",
        f"χ²({int(dof)}) = {chi2:.3f}, p = {p_format(p)}, Cramér's V = {v:.3f} ({mag}).",
        {"chi2": float(chi2), "p_value": float(p), "df": int(dof), "n": n, "cramers_v": v, "low_expected_cells": low_exp},
        (
            f"The test evaluates whether '{a}' and '{b}' are independent. "
            f"χ²={chi2:.3f} on {int(dof)} df, p={p_format(p)} ({sig_label(p)}). "
            f"Cramér's V={v:.3f} indicates a {mag} association. "
            "Independence testing is not a causal claim."
        ),
        tables={
            "observed": to_native(table),
            "expected": to_native(exp_df),
        },
        n=n,
        effect_size={"name": "Cramér's V", "value": v, "magnitude": mag},
        warnings=warns,
        formula="χ² = Σ (O−E)² / E;  V = √(χ² / (n·min(r−1,c−1)))",
    )


def fisher_exact(df, params):
    a, b = params.get("x"), params.get("y")
    tab = pd.crosstab(df[a], df[b])
    if tab.shape != (2, 2):
        raise ValueError("Fisher's exact test requires a 2×2 table. Recode variables to two levels each.")
    odds, p = stats.fisher_exact(tab.values)
    n = int(tab.values.sum())
    return result(
        "fisher_exact",
        "Fisher's exact test",
        f"Odds ratio = {odds:.3f}, p = {p_format(p)}, n = {n}.",
        {"odds_ratio": float(odds), "p_value": float(p), "n": n, "table": tab.values.tolist()},
        (
            f"Fisher's exact test (2×2) for '{a}' × '{b}': OR={odds:.3f}, p={p_format(p)} ({sig_label(p)}). "
            "The p-value is exact under fixed marginals; it does not rely on large-sample χ² approximation."
        ),
        tables={"observed": to_native(tab.reset_index())},
        n=n,
        formula="Hypergeometric probability of tables as or more extreme than observed",
    )


def cramers_v(df, params):
    r = chi_square(df, params)
    r["method"] = "cramers_v"
    r["method_label"] = "Cramér's V"
    return r


# ── Hypothesis tests ─────────────────────────────────────────


def one_sample_t(df, params):
    x = _num(df, params.get("y") or params.get("column"))
    mu = float(params.get("mu", 0))
    t, p = stats.ttest_1samp(x, mu)
    n = len(x)
    d = float((x.mean() - mu) / x.std(ddof=1)) if x.std(ddof=1) else 0
    lo, hi, se = _ci_mean(x)
    return result(
        "one_sample_t",
        "One-sample t-test",
        f"t({n-1}) = {t:.3f}, p = {p_format(p)}, mean = {x.mean():.4g} vs μ₀ = {mu}.",
        {
            "t": float(t),
            "p_value": float(p),
            "df": n - 1,
            "mean": float(x.mean()),
            "mu0": mu,
            "se": se,
            "ci95_low": lo,
            "ci95_high": hi,
            "n": n,
            "cohens_d": d,
        },
        (
            f"The sample mean of '{params.get('y') or params.get('column')}' is {x.mean():.4g} "
            f"(95% CI [{lo:.4g}, {hi:.4g}]). Testing H₀: μ = {mu} yields t({n-1})={t:.3f}, p={p_format(p)} "
            f"({sig_label(p)}). Cohen's d = {d:.3f}."
        ),
        n=n,
        effect_size={"name": "Cohen's d", "value": d},
        formula="t = (x̄ − μ₀) / (s/√n)",
    )


def independent_t(df, params):
    y, g = params.get("y"), params.get("x") or params.get("group")
    groups = _groups(df, y, g, params.get("levels"))
    if len(groups) != 2:
        raise ValueError(f"Independent t-test requires exactly 2 groups; found {len(groups)}: {list(groups)}")
    (n1, a), (n2, b) = [(k, v) for k, v in groups.items()]
    equal_var = bool(params.get("equal_var", True))
    # Levene
    W, plev = stats.levene(a, b)
    if plev < 0.05 and params.get("equal_var") is None:
        equal_var = False
    t, p = stats.ttest_ind(a, b, equal_var=equal_var)
    d = _cohens_d(a, b)
    n = len(a) + len(b)
    df_ = n - 2 if equal_var else None
    # Welch df
    if not equal_var:
        va, vb = a.var(ddof=1), b.var(ddof=1)
        na, nb = len(a), len(b)
        df_ = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    warns = []
    if plev < 0.05:
        warns.append(
            f"Levene's test suggests unequal variances (W={W:.3f}, p={p_format(plev)}). Welch's t-test is reported."
            if not equal_var
            else f"Levene's test p={p_format(plev)}; consider Welch's t-test."
        )
    if min(len(a), len(b)) < 15:
        warns.append("Small group size: t-test p-values are sensitive to non-normality. Inspect distributions or use Mann–Whitney U.")
    return result(
        "independent_t",
        "Independent-samples t-test" + ("" if equal_var else " (Welch)"),
        f"t({df_:.2f}) = {t:.3f}, p = {p_format(p)}, d = {d:.3f}. {n1}: n={len(a)}, mean={a.mean():.4g}; {n2}: n={len(b)}, mean={b.mean():.4g}.",
        {
            "t": float(t),
            "p_value": float(p),
            "df": float(df_),
            "equal_var": equal_var,
            "levene_W": float(W),
            "levene_p": float(plev),
            "mean_1": float(a.mean()),
            "mean_2": float(b.mean()),
            "sd_1": float(a.std(ddof=1)),
            "sd_2": float(b.std(ddof=1)),
            "n_1": int(len(a)),
            "n_2": int(len(b)),
            "group_1": n1,
            "group_2": n2,
            "mean_diff": float(a.mean() - b.mean()),
            "cohens_d": d,
            "hedges_g": _hedges_g(d, n),
        },
        (
            f"Comparing '{y}' between {n1} (n={len(a)}, mean={a.mean():.4g}) and {n2} "
            f"(n={len(b)}, mean={b.mean():.4g}). Mean difference = {a.mean()-b.mean():.4g}. "
            f"t={t:.3f}, df={df_:.2f}, p={p_format(p)} ({sig_label(p)}). "
            f"Cohen's d = {d:.3f} ({'small' if abs(d)<0.5 else 'medium' if abs(d)<0.8 else 'large'}). "
            "Statistical significance is not the same as practical importance."
        ),
        n=n,
        effect_size={"name": "Cohen's d", "value": d, "hedges_g": _hedges_g(d, n)},
        warnings=warns,
        formula="t = (x̄₁ − x̄₂) / (s_p √(1/n₁+1/n₂))  (Student) or Welch's unequal-variance form",
    )


def paired_t(df, params):
    a = _num(df, params.get("y") or params.get("before"))
    b = _num(df, params.get("x") or params.get("after"))
    n = min(len(a), len(b))
    # align by index intersection
    both = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if len(both) < 3:
        raise ValueError("Paired t-test needs at least 3 paired observations. Provide two numeric columns aligned by row.")
    t, p = stats.ttest_rel(both["a"], both["b"])
    diff = both["a"] - both["b"]
    d = float(diff.mean() / diff.std(ddof=1)) if diff.std(ddof=1) else 0
    lo, hi, se = _ci_mean(diff)
    return result(
        "paired_t",
        "Paired t-test",
        f"t({len(both)-1}) = {t:.3f}, p = {p_format(p)}, mean difference = {diff.mean():.4g}.",
        {
            "t": float(t),
            "p_value": float(p),
            "df": len(both) - 1,
            "mean_diff": float(diff.mean()),
            "sd_diff": float(diff.std(ddof=1)),
            "ci95_low": lo,
            "ci95_high": hi,
            "n": int(len(both)),
            "cohens_d": d,
        },
        (
            f"Paired comparison of '{params.get('y')}' vs '{params.get('x')}': mean difference {diff.mean():.4g} "
            f"(95% CI [{lo:.4g}, {hi:.4g}]). t({len(both)-1})={t:.3f}, p={p_format(p)} ({sig_label(p)}). "
            f"Cohen's d (paired) = {d:.3f}."
        ),
        n=int(len(both)),
        effect_size={"name": "Cohen's d (paired)", "value": d},
        formula="t = d̄ / (s_d / √n)",
    )


def z_test(df, params):
    x = _num(df, params.get("y") or params.get("column"))
    mu = float(params.get("mu", 0))
    sigma = float(params.get("sigma") or x.std(ddof=1))
    n = len(x)
    se = sigma / np.sqrt(n)
    z = (x.mean() - mu) / se
    p = 2 * stats.norm.sf(abs(z))
    return result(
        "z_test",
        "One-sample z-test",
        f"z = {z:.3f}, p = {p_format(p)}, mean = {x.mean():.4g}.",
        {"z": float(z), "p_value": float(p), "mean": float(x.mean()), "mu0": mu, "sigma": sigma, "n": n},
        f"z-test of H₀: μ={mu} with σ={sigma:.4g}. z={z:.3f}, p={p_format(p)} ({sig_label(p)}). "
        "A z-test is appropriate when σ is known or n is large; otherwise prefer a t-test.",
        n=n,
        warnings=["σ is rarely known in practice. Prefer the t-test unless σ is specified from theory or a large census."]
        if params.get("sigma") is None
        else [],
        formula="z = (x̄ − μ₀) / (σ/√n)",
    )


def mannwhitney(df, params):
    y, g = params.get("y"), params.get("x") or params.get("group")
    groups = _groups(df, y, g, params.get("levels"))
    if len(groups) != 2:
        raise ValueError(f"Mann–Whitney U requires exactly 2 groups; found {len(groups)}.")
    (n1, a), (n2, b) = list(groups.items())
    U, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    n = len(a) + len(b)
    rbc = 1 - (2 * U) / (len(a) * len(b))  # rank-biserial (sign depends on U definition)
    cles = U / (len(a) * len(b))
    return result(
        "mannwhitney",
        "Mann–Whitney U test",
        f"U = {U:.1f}, p = {p_format(p)}. {n1} n={len(a)} median={a.median():.4g}; {n2} n={len(b)} median={b.median():.4g}.",
        {
            "U": float(U),
            "p_value": float(p),
            "n_1": int(len(a)),
            "n_2": int(len(b)),
            "group_1": n1,
            "group_2": n2,
            "median_1": float(a.median()),
            "median_2": float(b.median()),
            "rank_biserial": float(rbc),
            "CLES": float(cles),
        },
        (
            f"Nonparametric comparison of '{y}' between {n1} and {n2}. "
            f"U={U:.1f}, p={p_format(p)} ({sig_label(p)}). "
            f"Common-language effect size (P(random {n1} > random {n2})) ≈ {cles:.3f}. "
            "Mann–Whitney tests stochastic dominance, not necessarily a difference in medians unless distributions have the same shape."
        ),
        n=n,
        effect_size={"name": "CLES", "value": float(cles)},
        formula="U = n₁ n₂ + n₁(n₁+1)/2 − R₁",
    )


def wilcoxon(df, params):
    both = pd.concat(
        [
            pd.to_numeric(df[params.get("y")], errors="coerce").rename("a"),
            pd.to_numeric(df[params.get("x")], errors="coerce").rename("b"),
        ],
        axis=1,
    ).dropna()
    diff = both["a"] - both["b"]
    diff = diff[diff != 0]
    if len(diff) < 6:
        raise ValueError("Wilcoxon signed-rank needs more non-zero paired differences.")
    W, p = stats.wilcoxon(diff)
    return result(
        "wilcoxon",
        "Wilcoxon signed-rank test",
        f"W = {W:.1f}, p = {p_format(p)}, n_nonzero = {len(diff)}.",
        {"W": float(W), "p_value": float(p), "n": int(len(diff)), "median_diff": float(diff.median())},
        f"Paired nonparametric test on '{params.get('y')}' vs '{params.get('x')}'. W={W:.1f}, p={p_format(p)} ({sig_label(p)}). "
        f"Median difference = {diff.median():.4g}. Zero differences were dropped.",
        n=int(len(diff)),
        formula="Signed-rank statistic of paired differences",
    )


def kruskal(df, params):
    y, g = params.get("y"), params.get("x") or params.get("group")
    groups = _groups(df, y, g, params.get("levels"))
    if len(groups) < 2:
        raise ValueError("Kruskal–Wallis requires ≥ 2 groups.")
    H, p = stats.kruskal(*groups.values())
    k = len(groups)
    n = sum(len(v) for v in groups.values())
    eta2 = float((H - k + 1) / (n - k)) if n > k else None
    med = [{"group": k_, "n": int(len(v)), "median": float(v.median()), "mean_rank": None} for k_, v in groups.items()]
    return result(
        "kruskal",
        "Kruskal–Wallis test",
        f"H = {H:.3f}, p = {p_format(p)}, k = {k}, n = {n}.",
        {"H": float(H), "p_value": float(p), "k": k, "n": n, "eta2_approx": eta2},
        f"Nonparametric comparison of '{y}' across {k} groups of '{g}'. H={H:.3f}, p={p_format(p)} ({sig_label(p)}). "
        "A significant result indicates at least one group stochastically differs; follow with Dunn post-hoc tests if needed.",
        tables={"groups": med},
        n=n,
        effect_size={"name": "ε² approx", "value": eta2},
    )


def friedman(df, params):
    cols = params.get("columns") or params.get("measures")
    if not cols or len(cols) < 3:
        raise ValueError("Friedman test needs ≥ 3 repeated-measure columns.")
    sub = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    chi2, p = stats.friedmanchisquare(*[sub[c] for c in cols])
    return result(
        "friedman",
        "Friedman test",
        f"χ² = {chi2:.3f}, p = {p_format(p)}, k = {len(cols)}, n = {len(sub)}.",
        {"chi2": float(chi2), "p_value": float(p), "k": len(cols), "n": int(len(sub))},
        f"Nonparametric repeated-measures comparison of {cols}. χ²={chi2:.3f}, p={p_format(p)} ({sig_label(p)}).",
        n=int(len(sub)),
    )


# ── ANOVA ────────────────────────────────────────────────────


def oneway_anova(df, params):
    y, g = params.get("y"), params.get("x") or params.get("group")
    groups = _groups(df, y, g, params.get("levels"))
    if len(groups) < 2:
        raise ValueError("ANOVA requires ≥ 2 groups.")
    F, p = stats.f_oneway(*groups.values())
    k = len(groups)
    n = sum(len(v) for v in groups.values())
    # eta squared via SS
    allv = np.concatenate([v.values for v in groups.values()])
    gm = allv.mean()
    ssb = sum(len(v) * (v.mean() - gm) ** 2 for v in groups.values())
    ssw = sum(((v - v.mean()) ** 2).sum() for v in groups.values())
    sst = ssb + ssw
    eta2 = float(ssb / sst) if sst else 0
    omega2 = float((ssb - (k - 1) * (ssw / max(n - k, 1))) / (sst + (ssw / max(n - k, 1)))) if n > k else None
    W, plev = stats.levene(*groups.values())
    rows = [
        {"group": name, "n": int(len(v)), "mean": float(v.mean()), "sd": float(v.std(ddof=1)), "median": float(v.median())}
        for name, v in groups.items()
    ]
    warns = []
    if plev < 0.05:
        warns.append(f"Levene p={p_format(plev)}: variances may be unequal. Consider Welch ANOVA or Kruskal–Wallis.")
    if any(len(v) < 5 for v in groups.values()):
        warns.append("At least one group has n < 5; ANOVA F is sensitive in small samples.")
    return result(
        "oneway_anova",
        "One-way ANOVA",
        f"F({k-1}, {n-k}) = {F:.3f}, p = {p_format(p)}, η² = {eta2:.3f}.",
        {
            "F": float(F),
            "p_value": float(p),
            "df_between": k - 1,
            "df_within": n - k,
            "eta_squared": eta2,
            "omega_squared": omega2,
            "levene_W": float(W),
            "levene_p": float(plev),
            "ss_between": float(ssb),
            "ss_within": float(ssw),
            "k": k,
            "n": n,
        },
        (
            f"One-way ANOVA of '{y}' by '{g}': F({k-1},{n-k})={F:.3f}, p={p_format(p)} ({sig_label(p)}). "
            f"η²={eta2:.3f} (proportion of variance in {y} associated with {g}). "
            "A significant F indicates at least one mean differs; inspect Tukey HSD for pairwise comparisons. "
            "Do not interpret a significant ANOVA as every group differing from every other group."
        ),
        tables={"group_summaries": rows},
        n=n,
        effect_size={"name": "eta_squared", "value": eta2, "omega_squared": omega2},
        warnings=warns,
        formula="F = MS_between / MS_within",
    )


def tukey_hsd(df, params):
    y, g = params.get("y"), params.get("x") or params.get("group")
    tmp = df[[y, g]].dropna()
    tmp[y] = pd.to_numeric(tmp[y], errors="coerce")
    tmp = tmp.dropna()
    from statsmodels.stats.multicomp import pairwise_tukeyhsd

    res = pairwise_tukeyhsd(tmp[y], tmp[g].astype(str), alpha=float(params.get("alpha", 0.05)))
    data = res.summary().data
    headers, rows = data[0], data[1:]
    table = [dict(zip(headers, row)) for row in rows]
    return result(
        "tukey_hsd",
        "Tukey HSD pairwise comparisons",
        f"Tukey HSD for '{y}' by '{g}' ({len(table)} pairs).",
        {"alpha": float(params.get("alpha", 0.05)), "n_pairs": len(table)},
        "Tukey HSD controls the family-wise error rate for all pairwise mean comparisons after ANOVA. "
        "Reject H₀ for a pair when 'reject' is true (adjusted p < α).",
        tables={"comparisons": to_native(table)},
        n=int(len(tmp)),
        warnings=["Tukey HSD assumes equal variances and (approximately) normality."],
    )


def twoway_anova(df, params):
    y = params.get("y")
    f1, f2 = params.get("factor1") or params.get("x"), params.get("factor2") or params.get("group")
    if not f1 or not f2:
        raise ValueError("Two-way ANOVA requires y, factor1, and factor2.")
    import statsmodels.api as sm
    from statsmodels.formula.api import ols

    tmp = df[[y, f1, f2]].dropna().copy()
    tmp[y] = pd.to_numeric(tmp[y], errors="coerce")
    tmp = tmp.dropna()
    tmp = tmp.rename(columns={y: "Y", f1: "A", f2: "B"})
    formula = "Y ~ C(A) + C(B) + C(A):C(B)"
    model = ols(formula, data=tmp).fit()
    tbl = sm.stats.anova_lm(model, typ=2)
    table = tbl.reset_index().rename(columns={"index": "term"})
    return result(
        "twoway_anova",
        "Two-way ANOVA",
        f"Two-way ANOVA of '{y}' ~ {f1} * {f2}. See term-wise F tests.",
        {"formula": f"{y} ~ {f1} * {f2}", "n": int(len(tmp)), "r2": float(model.rsquared)},
        f"Type II ANOVA partitions variance in '{y}' into {f1}, {f2}, and their interaction. "
        "Interpret the interaction first: if it is significant, simple effects are more appropriate than main effects.",
        tables={"anova": to_native(table), "params": to_native(model.summary2().tables[1].reset_index())},
        n=int(len(tmp)),
        formula=formula,
    )


def ancova(df, params):
    y = params.get("y")
    g = params.get("x") or params.get("group")
    cov = params.get("covariate")
    if not cov:
        raise ValueError("ANCOVA requires a covariate.")
    import pingouin as pg

    tmp = df[[y, g, cov]].dropna().copy()
    tmp[y] = pd.to_numeric(tmp[y], errors="coerce")
    tmp[cov] = pd.to_numeric(tmp[cov], errors="coerce")
    tmp = tmp.dropna()
    aov = pg.ancova(data=tmp, dv=y, between=g, covar=cov)
    return result(
        "ancova",
        "ANCOVA",
        f"ANCOVA of '{y}' by '{g}' adjusting for '{cov}'.",
        {"n": int(len(tmp))},
        f"ANCOVA tests group differences in '{y}' after linearly adjusting for '{cov}'. "
        "Assumes parallel slopes (no group × covariate interaction) and a linear covariate relationship.",
        tables={"ancova": to_native(aov)},
        n=int(len(tmp)),
        warnings=["Verify the homogeneity-of-regression-slopes assumption (group × covariate interaction)."],
    )


def repeated_anova(df, params):
    cols = params.get("columns") or params.get("measures")
    if not cols or len(cols) < 2:
        raise ValueError("Repeated-measures ANOVA needs ≥ 2 measure columns (wide format).")
    import pingouin as pg

    tmp = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    tmp = tmp.copy()
    tmp["subject"] = np.arange(len(tmp))
    long = tmp.melt(id_vars="subject", value_vars=cols, var_name="time", value_name="dv")
    aov = pg.rm_anova(data=long, dv="dv", within="time", subject="subject", detailed=True)
    sph = None
    try:
        sph = pg.sphericity(data=long, dv="dv", within="time", subject="subject")
        sph = {"W": float(sph[0]) if not isinstance(sph[0], tuple) else None, "pval": float(sph.pval) if hasattr(sph, "pval") else None}
    except Exception:
        sph = None
    return result(
        "repeated_anova",
        "Repeated-measures ANOVA",
        f"RM-ANOVA across {len(cols)} occasions (n={len(tmp)} subjects).",
        {"n_subjects": int(len(tmp)), "k": len(cols), "sphericity": sph},
        "Repeated-measures ANOVA tests whether means change across occasions within subjects. "
        "If sphericity is violated, use Greenhouse–Geisser or Huynh–Feldt corrected p-values (shown when available).",
        tables={"anova": to_native(aov)},
        n=int(len(tmp)),
    )


# ── Regression ───────────────────────────────────────────────


def _fit_ols(df, y, xs, robust=False):
    import statsmodels.api as sm

    tmp = df[[y] + xs].copy()
    for c in [y] + xs:
        tmp[c] = pd.to_numeric(tmp[c], errors="coerce")
    tmp = tmp.dropna()
    if len(tmp) < len(xs) + 3:
        raise ValueError("Not enough complete cases for regression.")
    X = sm.add_constant(tmp[xs], has_constant="add")
    model = sm.OLS(tmp[y], X)
    if robust:
        fit = model.fit(cov_type="HC3")
    else:
        fit = model.fit()
    return fit, tmp


def _reg_table(fit):
    ci = fit.conf_int()
    rows = []
    for name in fit.params.index:
        rows.append(
            {
                "term": str(name),
                "coef": float(fit.params[name]),
                "se": float(fit.bse[name]),
                "t": float(fit.tvalues[name]),
                "p_value": float(fit.pvalues[name]),
                "ci95_low": float(ci.loc[name, 0]),
                "ci95_high": float(ci.loc[name, 1]),
            }
        )
    return rows


def linear_regression(df, params):
    y = params.get("y")
    xs = params.get("x")
    if isinstance(xs, str):
        xs = [xs]
    xs = xs or params.get("predictors")
    if not xs:
        raise ValueError("Provide predictor column(s).")
    robust = bool(params.get("robust"))
    fit, tmp = _fit_ols(df, y, list(xs), robust=robust)
    # VIF
    vif_rows = []
    if len(xs) >= 2:
        from statsmodels.stats.outliers_influence import variance_inflation_factor
        import statsmodels.api as sm

        X = sm.add_constant(tmp[xs], has_constant="add")
        for i, name in enumerate(X.columns):
            if name == "const":
                continue
            vif_rows.append({"term": name, "VIF": float(variance_inflation_factor(X.values, i))})
    resid = fit.resid
    jb_stat = jb_p = None
    try:
        from statsmodels.stats.stattools import jarque_bera

        jb_stat, jb_p, _, _ = jarque_bera(resid)
    except Exception:
        pass
    bp_p = None
    try:
        import statsmodels.api as sm
        from statsmodels.stats.diagnostic import het_breuschpagan

        bp = het_breuschpagan(resid, fit.model.exog)
        bp_p = float(bp[1])
    except Exception:
        pass
    method = "robust_regression" if robust else ("multiple_regression" if len(xs) > 1 else "linear_regression")
    label = "Robust linear regression (HC3)" if robust else ("Multiple linear regression" if len(xs) > 1 else "Simple linear regression")
    warns = []
    if any(v["VIF"] > 5 for v in vif_rows):
        warns.append("One or more predictors have VIF > 5 (multicollinearity). Coefficients may be unstable.")
    if bp_p is not None and bp_p < 0.05:
        warns.append(f"Breusch–Pagan p={p_format(bp_p)}: possible heteroscedasticity. Consider robust SEs or a transformation.")
    if fit.nobs < 10 * (len(xs) + 1):
        warns.append("Rule of thumb: fewer than ~10 observations per parameter. Estimates may be imprecise.")
    return result(
        method,
        label,
        f"R² = {fit.rsquared:.3f}, adj. R² = {fit.rsquared_adj:.3f}, F p = {p_format(fit.f_pvalue)}, n = {int(fit.nobs)}.",
        {
            "r2": float(fit.rsquared),
            "r2_adj": float(fit.rsquared_adj),
            "fvalue": float(fit.fvalue) if fit.fvalue is not None else None,
            "f_pvalue": float(fit.f_pvalue) if fit.f_pvalue is not None else None,
            "aic": float(fit.aic),
            "bic": float(fit.bic),
            "n": int(fit.nobs),
            "df_model": float(fit.df_model),
            "df_resid": float(fit.df_resid),
            "residual_std": float(np.sqrt(fit.mse_resid)),
        },
        (
            f"{label} of '{y}' on {', '.join(xs)}. "
            f"The model explains {fit.rsquared*100:.1f}% of sample variance in {y} (adj. R²={fit.rsquared_adj:.3f}). "
            f"Overall F p={p_format(fit.f_pvalue)}. Inspect coefficients, residual plots, and assumptions before interpreting. "
            "Coefficients are associations conditional on the included predictors, not causal effects unless the design supports that claim."
        ),
        tables={"coefficients": _reg_table(fit), "vif": vif_rows},
        n=int(fit.nobs),
        model_diagnostics={
            "jarque_bera": jb_stat,
            "jarque_bera_p": jb_p,
            "breusch_pagan_p": bp_p,
            "durbin_watson": float(np.sum(np.diff(resid) ** 2) / np.sum(resid**2)) if len(resid) > 2 else None,
        },
        warnings=warns,
        formula=f"{y} ~ " + " + ".join(xs),
    )


def polynomial_regression(df, params):
    y, x = params.get("y"), params.get("x")
    deg = int(params.get("degree", 2))
    tmp = df[[y, x]].copy()
    tmp[y] = pd.to_numeric(tmp[y], errors="coerce")
    tmp[x] = pd.to_numeric(tmp[x], errors="coerce")
    tmp = tmp.dropna()
    for d in range(2, deg + 1):
        tmp[f"{x}^{d}"] = tmp[x] ** d
    xs = [x] + [f"{x}^{d}" for d in range(2, deg + 1)]
    params2 = {"y": y, "x": xs}
    r = linear_regression(tmp, params2)
    r["method"] = "polynomial_regression"
    r["method_label"] = f"Polynomial regression (degree {deg})"
    r["formula"] = f"{y} ~ poly({x}, {deg})"
    return r


def logistic_regression(df, params):
    import statsmodels.api as sm

    y = params.get("y")
    xs = params.get("x")
    if isinstance(xs, str):
        xs = [xs]
    tmp = df[[y] + list(xs)].copy()
    for c in xs:
        tmp[c] = pd.to_numeric(tmp[c], errors="coerce")
    tmp[y] = pd.to_numeric(tmp[y], errors="coerce")
    # if y not 0/1, try mapping
    uniq = tmp[y].dropna().unique()
    if not set(np.unique(uniq)).issubset({0, 1, 0.0, 1.0}):
        if len(uniq) == 2:
            mapping = {uniq[0]: 0, uniq[1]: 1}
            tmp[y] = tmp[y].map(mapping)
        else:
            raise ValueError("Logistic regression requires a binary outcome (two levels).")
    tmp = tmp.dropna()
    X = sm.add_constant(tmp[list(xs)], has_constant="add")
    fit = sm.Logit(tmp[y], X).fit(disp=False)
    ci = fit.conf_int()
    rows = []
    for name in fit.params.index:
        rows.append(
            {
                "term": str(name),
                "coef": float(fit.params[name]),
                "se": float(fit.bse[name]),
                "z": float(fit.tvalues[name]),
                "p_value": float(fit.pvalues[name]),
                "or": float(np.exp(fit.params[name])),
                "or_ci95_low": float(np.exp(ci.loc[name, 0])),
                "or_ci95_high": float(np.exp(ci.loc[name, 1])),
            }
        )
    return result(
        "logistic_regression",
        "Logistic regression",
        f"Logistic model of '{y}'. Pseudo-R²={float(fit.prsquared):.3f}, AIC={float(fit.aic):.1f}, n={int(fit.nobs)}.",
        {
            "prsquared": float(fit.prsquared),
            "aic": float(fit.aic),
            "bic": float(fit.bic),
            "llf": float(fit.llf),
            "n": int(fit.nobs),
            "converged": bool(fit.mle_retvals.get("converged", True)),
        },
        (
            f"Binary logistic regression of '{y}' on {', '.join(xs)}. Coefficients are log-odds; odds ratios are exp(β). "
            f"McFadden pseudo-R²={float(fit.prsquared):.3f}. This is not ordinary R² and should not be interpreted as variance explained."
        ),
        tables={"coefficients": rows},
        n=int(fit.nobs),
        formula=f"logit(P({y}=1)) ~ " + " + ".join(xs),
    )


def poisson_regression(df, params):
    import statsmodels.api as sm

    y = params.get("y")
    xs = params.get("x")
    if isinstance(xs, str):
        xs = [xs]
    tmp = df[[y] + list(xs)].apply(pd.to_numeric, errors="coerce").dropna()
    X = sm.add_constant(tmp[list(xs)], has_constant="add")
    fit = sm.GLM(tmp[y], X, family=sm.families.Poisson()).fit()
    # overdispersion
    disp = float(fit.deviance / max(fit.df_resid, 1))
    warns = []
    if disp > 1.5:
        warns.append(f"Deviance/df = {disp:.2f} suggests overdispersion. Consider negative binomial regression.")
    return result(
        "poisson_regression",
        "Poisson regression",
        f"Poisson GLM of '{y}'. Deviance={float(fit.deviance):.2f}, AIC={float(fit.aic):.1f}, n={int(fit.nobs)}.",
        {"deviance": float(fit.deviance), "pearson_chi2": float(fit.pearson_chi2), "dispersion": disp, "aic": float(fit.aic), "n": int(fit.nobs)},
        f"Poisson regression models a count outcome. Coefficients are log-rate ratios. Dispersion statistic = {disp:.2f}.",
        tables={"coefficients": _reg_table(fit)},
        n=int(fit.nobs),
        warnings=warns,
        formula=f"log(E[{y}]) ~ " + " + ".join(xs),
    )


def negative_binomial(df, params):
    import statsmodels.api as sm

    y = params.get("y")
    xs = params.get("x")
    if isinstance(xs, str):
        xs = [xs]
    tmp = df[[y] + list(xs)].apply(pd.to_numeric, errors="coerce").dropna()
    X = sm.add_constant(tmp[list(xs)], has_constant="add")
    fit = sm.GLM(tmp[y], X, family=sm.families.NegativeBinomial()).fit()
    return result(
        "negative_binomial",
        "Negative binomial regression",
        f"NB GLM of '{y}'. Deviance={float(fit.deviance):.2f}, AIC={float(fit.aic):.1f}, n={int(fit.nobs)}.",
        {"deviance": float(fit.deviance), "aic": float(fit.aic), "n": int(fit.nobs)},
        "Negative binomial regression is appropriate for overdispersed counts. Coefficients are log-mean ratios.",
        tables={"coefficients": _reg_table(fit)},
        n=int(fit.nobs),
    )


def robust_regression(df, params):
    params = {**params, "robust": True}
    return linear_regression(df, params)


# ── Time series ──────────────────────────────────────────────


def _ts(df, params):
    y = params.get("y") or params.get("column")
    t = params.get("time")
    if t and t in df.columns:
        tmp = df[[t, y]].copy()
        tmp[t] = pd.to_datetime(tmp[t], errors="coerce")
        tmp[y] = pd.to_numeric(tmp[y], errors="coerce")
        tmp = tmp.dropna().sort_values(t)
        s = tmp.set_index(t)[y]
    else:
        s = pd.to_numeric(df[y], errors="coerce").dropna()
        s.index = pd.RangeIndex(len(s))
    return s, y, t


def moving_average(df, params):
    s, y, t = _ts(df, params)
    w = int(params.get("window", 7))
    ma = s.rolling(w, min_periods=max(1, w // 2)).mean()
    out = pd.DataFrame({"time": s.index.astype(str), y: s.values, f"ma_{w}": ma.values})
    return result(
        "moving_average",
        f"Moving average (window={w})",
        f"Rolling mean of '{y}' with window {w}.",
        {"window": w, "n": int(s.notna().sum())},
        "A moving average is a smoother, not a statistical test. Edge values are less stable.",
        tables={"series": to_native(out.tail(400))},
        n=int(len(s)),
    )


def trend_analysis(df, params):
    s, y, t = _ts(df, params)
    x = np.arange(len(s), dtype=float)
    slope, intercept, r, p, se = stats.linregress(x, s.values.astype(float))
    return result(
        "trend_analysis",
        "Linear trend",
        f"Slope = {slope:.4g} per time step, r = {r:.3f}, p = {p_format(p)}.",
        {"slope": float(slope), "intercept": float(intercept), "r": float(r), "p_value": float(p), "se": float(se), "n": int(len(s))},
        f"A linear time index was regressed on '{y}'. Slope={slope:.4g} per observation, p={p_format(p)} ({sig_label(p)}). "
        "This does not model seasonality or autocorrelation; residual dependence would invalidate the p-value.",
        n=int(len(s)),
        warnings=["Time-series observations are often dependent. Treat this p-value as descriptive unless residuals are uncorrelated."],
    )


def acf_pacf(df, params):
    import statsmodels.api as sm

    s, y, t = _ts(df, params)
    nl = int(params.get("nlags", min(24, max(5, len(s) // 4))))
    acf = sm.tsa.acf(s.values, nlags=nl, fft=True)
    pacf = sm.tsa.pacf(s.values, nlags=nl)
    table = [{"lag": int(i), "acf": float(acf[i]), "pacf": float(pacf[i])} for i in range(len(acf))]
    return result(
        "acf_pacf",
        "ACF / PACF",
        f"Autocorrelation structure of '{y}' up to lag {nl}.",
        {"nlags": nl, "n": int(len(s))},
        "Significant ACF at lag k indicates association k steps apart. PACF helps identify AR order. "
        "Use these as diagnostics for ARIMA identification, not as hypothesis tests of a scientific claim.",
        tables={"lags": table},
        n=int(len(s)),
    )


def arima_model(df, params):
    from statsmodels.tsa.arima.model import ARIMA

    s, y, t = _ts(df, params)
    order = tuple(params.get("order") or (1, 1, 1))
    steps = int(params.get("steps", 12))
    model = ARIMA(s.astype(float), order=order)
    fit = model.fit()
    fc = fit.get_forecast(steps=steps)
    pred = fc.predicted_mean
    ci = fc.conf_int()
    ftable = []
    for i, (idx, val) in enumerate(pred.items()):
        ftable.append(
            {
                "step": i + 1,
                "time": str(idx),
                "forecast": float(val),
                "ci95_low": float(ci.iloc[i, 0]),
                "ci95_high": float(ci.iloc[i, 1]),
            }
        )
    return result(
        "arima",
        f"ARIMA{order}",
        f"ARIMA{order} of '{y}'. AIC={fit.aic:.1f}, BIC={fit.bic:.1f}.",
        {"order": list(order), "aic": float(fit.aic), "bic": float(fit.bic), "n": int(fit.nobs)},
        f"ARIMA{order} was fit by maximum likelihood. Forecasts assume the identified structure continues. "
        "Always inspect ACF of residuals; do not treat forecasts as guaranteed future values.",
        tables={"forecast": ftable, "params": [{"term": str(k), "coef": float(v)} for k, v in fit.params.items()]},
        n=int(fit.nobs),
        formula=f"ARIMA{order}",
    )


def sarima_model(df, params):
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    s, y, t = _ts(df, params)
    order = tuple(params.get("order") or (1, 1, 1))
    seasonal = tuple(params.get("seasonal_order") or (1, 1, 1, 12))
    steps = int(params.get("steps", 12))
    fit = SARIMAX(s.astype(float), order=order, seasonal_order=seasonal, enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
    fc = fit.get_forecast(steps=steps)
    pred = fc.predicted_mean
    ci = fc.conf_int()
    ftable = [
        {
            "step": i + 1,
            "time": str(idx),
            "forecast": float(val),
            "ci95_low": float(ci.iloc[i, 0]),
            "ci95_high": float(ci.iloc[i, 1]),
        }
        for i, (idx, val) in enumerate(pred.items())
    ]
    return result(
        "sarima",
        f"SARIMA{order}x{seasonal}",
        f"SARIMA{order}×{seasonal} AIC={fit.aic:.1f}.",
        {"order": list(order), "seasonal_order": list(seasonal), "aic": float(fit.aic), "bic": float(fit.bic)},
        "Seasonal ARIMA captures repeating cycles (e.g. 12 for monthly data). Forecast intervals assume correct specification.",
        tables={"forecast": ftable},
        n=int(fit.nobs),
    )


def exp_smoothing(df, params):
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    s, y, t = _ts(df, params)
    seasonal_periods = params.get("seasonal_periods")
    trend = params.get("trend", "add")
    seasonal = params.get("seasonal")
    kw = {"trend": trend}
    if seasonal and seasonal_periods:
        kw["seasonal"] = seasonal
        kw["seasonal_periods"] = int(seasonal_periods)
    fit = ExponentialSmoothing(s.astype(float), **kw).fit()
    steps = int(params.get("steps", 12))
    fc = fit.forecast(steps)
    return result(
        "exp_smoothing",
        "Exponential smoothing",
        f"Holt–Winters / exponential smoothing of '{y}'. SSE={float(fit.sse):.4g}.",
        {"sse": float(fit.sse), "n": int(len(s))},
        "Exponential smoothing forecasts by weighting recent observations more heavily. It is a forecasting heuristic with statistical underpinnings, not a causal model.",
        tables={"forecast": [{"step": i + 1, "forecast": float(v)} for i, v in enumerate(fc)]},
        n=int(len(s)),
    )


def seasonality(df, params):
    s, y, t = _ts(df, params)
    period = int(params.get("period", 12))
    if len(s) < period * 2:
        raise ValueError("Need at least two full periods to inspect seasonality.")
    arr = np.asarray(s, float)
    n = (len(arr) // period) * period
    arr = arr[:n].reshape(-1, period)
    seasonal = arr.mean(axis=0)
    return result(
        "seasonality",
        "Seasonal profile",
        f"Mean seasonal profile of '{y}' with period {period}.",
        {"period": period, "seasonal_amplitude": float(np.nanmax(seasonal) - np.nanmin(seasonal))},
        "The seasonal profile is the mean of each position in the cycle. It is descriptive; use SARIMA or STL for formal decomposition.",
        tables={"profile": [{"season": i + 1, "mean": float(v)} for i, v in enumerate(seasonal)]},
        n=int(n),
    )


# ── Multivariate ─────────────────────────────────────────────


def pca_analysis(df, params):
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    cols = params.get("columns") or [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    X = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if X.shape[1] < 2:
        raise ValueError("PCA needs at least 2 numeric columns.")
    Z = StandardScaler().fit_transform(X)
    k = int(params.get("n_components") or min(5, X.shape[1]))
    pca = PCA(n_components=k)
    scores = pca.fit_transform(Z)
    load = pd.DataFrame(pca.components_.T, index=cols, columns=[f"PC{i+1}" for i in range(k)]).reset_index().rename(columns={"index": "variable"})
    var = [
        {"component": f"PC{i+1}", "eigenvalue": float(pca.explained_variance_[i]), "var_pct": float(pca.explained_variance_ratio_[i] * 100), "cum_pct": float(pca.explained_variance_ratio_[: i + 1].sum() * 100)}
        for i in range(k)
    ]
    sc = pd.DataFrame(scores[:, : min(3, k)], columns=[f"PC{i+1}" for i in range(min(3, k))])
    return result(
        "pca",
        "Principal component analysis",
        f"PCA on {len(cols)} standardized variables. PC1 explains {pca.explained_variance_ratio_[0]*100:.1f}% of variance.",
        {"n": int(len(X)), "p": len(cols), "n_components": k},
        "PCA is an unsupervised rotation of standardized variables. Components are not latent 'causes' unless a measurement model is justified. Interpret loadings with care.",
        tables={"variance": var, "loadings": to_native(load), "scores_head": to_native(sc.head(50))},
        n=int(len(X)),
    )


def factor_analysis(df, params):
    from sklearn.decomposition import FactorAnalysis
    from sklearn.preprocessing import StandardScaler

    cols = params.get("columns") or [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    X = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    k = int(params.get("n_factors") or min(3, max(1, X.shape[1] // 2)))
    Z = StandardScaler().fit_transform(X)
    fa = FactorAnalysis(n_components=k, random_state=0)
    fa.fit(Z)
    load = pd.DataFrame(fa.components_.T, index=cols, columns=[f"F{i+1}" for i in range(k)]).reset_index().rename(columns={"index": "variable"})
    return result(
        "factor_analysis",
        "Exploratory factor analysis",
        f"EFA with {k} factors on {len(cols)} variables (n={len(X)}).",
        {"n": int(len(X)), "n_factors": k, "noise_variance": to_native(dict(zip(cols, fa.noise_variance_)))},
        "Exploratory factor analysis models shared latent variance. The number of factors is a modeling choice; triangulate with theory, eigenvalues, and interpretability. This is not confirmatory factor analysis.",
        tables={"loadings": to_native(load)},
        n=int(len(X)),
    )


def kmeans_cluster(df, params):
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import silhouette_score

    cols = params.get("columns") or [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    X = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    k = int(params.get("k", 3))
    Z = StandardScaler().fit_transform(X)
    km = KMeans(n_clusters=k, n_init=10, random_state=0)
    labels = km.fit_predict(Z)
    sil = float(silhouette_score(Z, labels)) if k > 1 and len(X) > k else None
    centers = pd.DataFrame(km.cluster_centers_, columns=cols)
    centers.insert(0, "cluster", range(k))
    sizes = pd.Series(labels).value_counts().sort_index()
    return result(
        "kmeans",
        f"K-means clustering (k={k})",
        f"k-means with k={k}. Inertia={float(km.inertia_):.2f}, silhouette={sil if sil is not None else 'n/a'}.",
        {"k": k, "inertia": float(km.inertia_), "silhouette": sil, "n": int(len(X)), "sizes": {int(i): int(c) for i, c in sizes.items()}},
        "k-means partitions standardized observations into spherical clusters. The value of k is not estimated as a hypothesis test. "
        "Silhouette values near 1 indicate coherent clusters; near 0 indicate overlap. Clustering is unsupervised and not a confirmatory grouping test.",
        tables={"centers": to_native(centers), "sizes": [{"cluster": int(i), "n": int(c)} for i, c in sizes.items()]},
        n=int(len(X)),
    )


def manova(df, params):
    dvs = params.get("dvs") or params.get("columns")
    g = params.get("group") or params.get("x")
    if not dvs or not g:
        raise ValueError("MANOVA requires multiple DVs and a grouping factor.")
    from statsmodels.multivariate.manova import MANOVA

    tmp = df[list(dvs) + [g]].dropna().copy()
    for c in dvs:
        tmp[c] = pd.to_numeric(tmp[c], errors="coerce")
    tmp = tmp.dropna()
    formula = " + ".join([f"Q('{c}')" for c in dvs]) + f" ~ C(Q('{g}'))"
    # simpler names
    rename = {c: f"y{i}" for i, c in enumerate(dvs)}
    tmp2 = tmp.rename(columns=rename)
    tmp2["G"] = tmp2[g].astype(str)
    formula = " + ".join(rename.values()) + " ~ C(G)"
    mv = MANOVA.from_formula(formula, data=tmp2)
    out = mv.mv_test()
    # parse
    try:
        stat = out.results["C(G)"]["stat"]
        table = stat.reset_index()
    except Exception:
        table = [{"note": str(out)}]
    return result(
        "manova",
        "MANOVA",
        f"MANOVA of {len(dvs)} outcomes by '{g}' (n={len(tmp)}).",
        {"n": int(len(tmp)), "p": len(dvs)},
        "MANOVA tests whether group mean vectors differ. Follow significant results with univariate ANOVAs and/or discriminant analysis, with multiplicity in mind.",
        tables={"mv_test": to_native(table) if not isinstance(table, list) else table},
        n=int(len(tmp)),
    )


def lda_analysis(df, params):
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import accuracy_score

    y = params.get("y") or params.get("group")
    cols = params.get("columns") or [c for c in df.columns if c != y and pd.api.types.is_numeric_dtype(df[c])]
    tmp = df[cols + [y]].dropna()
    X = StandardScaler().fit_transform(tmp[cols].apply(pd.to_numeric, errors="coerce"))
    yv = tmp[y].astype(str)
    lda = LinearDiscriminantAnalysis()
    lda.fit(X, yv)
    pred = lda.predict(X)
    acc = float(accuracy_score(yv, pred))
    return result(
        "lda",
        "Linear discriminant analysis",
        f"LDA classifying '{y}' from {len(cols)} predictors. In-sample accuracy={acc:.3f}.",
        {"n": int(len(tmp)), "accuracy_in_sample": acc, "n_classes": int(yv.nunique()), "priors": to_native(lda.priors_)},
        "In-sample accuracy is optimistic. Use cross-validation for honest predictive performance. LDA assumes multivariate normality and equal covariance matrices.",
        n=int(len(tmp)),
        warnings=["Reported accuracy is in-sample and overestimates generalization."],
        tables={"classes": [{"class": str(c), "n": int((yv == c).sum())} for c in yv.unique()]},
    )


# ── Nonparametric extras ─────────────────────────────────────


def bootstrap_ci(df, params):
    col = params.get("column") or params.get("y")
    stat = params.get("stat", "mean")
    x = _num(df, col).values
    n_boot = int(params.get("n_boot", 2000))
    rng = np.random.default_rng(0)

    def fn(a):
        return {"mean": np.mean, "median": np.median, "std": lambda z: np.std(z, ddof=1)}[stat](a)

    obs = float(fn(x))
    boots = np.empty(n_boot)
    n = len(x)
    for i in range(n_boot):
        boots[i] = fn(rng.choice(x, size=n, replace=True))
    lo, hi = np.quantile(boots, [0.025, 0.975])
    return result(
        "bootstrap_ci",
        f"Bootstrap 95% CI ({stat})",
        f"{stat} = {obs:.4g}, 95% percentile bootstrap CI [{lo:.4g}, {hi:.4g}] ({n_boot} resamples).",
        {"estimate": obs, "ci95_low": float(lo), "ci95_high": float(hi), "n_boot": n_boot, "n": n, "stat": stat},
        "Percentile bootstrap CIs do not assume normality of the estimator. They can be biased for extreme quantiles or very small n.",
        n=n,
        confidence_intervals={stat: [float(lo), float(hi)]},
    )


def permutation_test(df, params):
    y, g = params.get("y"), params.get("x") or params.get("group")
    groups = _groups(df, y, g, params.get("levels"))
    if len(groups) != 2:
        raise ValueError("This permutation test compares two groups.")
    (n1, a), (n2, b) = list(groups.items())
    a, b = a.values, b.values
    obs = float(a.mean() - b.mean())
    pooled = np.concatenate([a, b])
    n_a = len(a)
    n_perm = int(params.get("n_perm", 2000))
    rng = np.random.default_rng(0)
    count = 0
    for _ in range(n_perm):
        rng.shuffle(pooled)
        d = pooled[:n_a].mean() - pooled[n_a:].mean()
        if abs(d) >= abs(obs):
            count += 1
    p = (count + 1) / (n_perm + 1)
    return result(
        "permutation_test",
        "Two-group permutation test (mean difference)",
        f"Observed mean difference = {obs:.4g}, Monte Carlo p = {p_format(p)} ({n_perm} permutations).",
        {"mean_diff": obs, "p_value": float(p), "n_perm": n_perm, "group_1": n1, "group_2": n2, "n_1": len(a), "n_2": len(b)},
        "The permutation test assesses whether group labels are exchangeable under H₀. The p-value includes the +1 continuity correction.",
        n=len(a) + len(b),
        formula="P(|Δ*| ≥ |Δ_obs|) under random reassignment of labels",
    )


# ── Survival ─────────────────────────────────────────────────


def kaplan_meier(df, params):
    from lifelines import KaplanMeierFitter

    dur = params.get("duration") or params.get("y")
    ev = params.get("event")
    g = params.get("group") or params.get("x")
    tmp = df[[dur, ev] + ([g] if g else [])].copy()
    tmp[dur] = pd.to_numeric(tmp[dur], errors="coerce")
    tmp[ev] = pd.to_numeric(tmp[ev], errors="coerce")
    tmp = tmp.dropna(subset=[dur, ev])
    kmf = KaplanMeierFitter()
    curves = []
    if g:
        for name, part in tmp.groupby(g):
            kmf.fit(part[dur], part[ev], label=str(name))
            sf = kmf.survival_function_.reset_index()
            sf.columns = ["time", "survival"]
            sf["group"] = str(name)
            curves.append(sf)
            med = kmf.median_survival_time_
        curves_df = pd.concat(curves, ignore_index=True)
        medians = []
        for name, part in tmp.groupby(g):
            kmf.fit(part[dur], part[ev], label=str(name))
            medians.append({"group": str(name), "n": int(len(part)), "events": int(part[ev].sum()), "median_survival": to_native(kmf.median_survival_time_)})
    else:
        kmf.fit(tmp[dur], tmp[ev], label="all")
        sf = kmf.survival_function_.reset_index()
        sf.columns = ["time", "survival"]
        sf["group"] = "all"
        curves_df = sf
        medians = [{"group": "all", "n": int(len(tmp)), "events": int(tmp[ev].sum()), "median_survival": to_native(kmf.median_survival_time_)}]
    return result(
        "kaplan_meier",
        "Kaplan–Meier survival",
        f"Kaplan–Meier estimate of survival for '{dur}' (event='{ev}'), n={len(tmp)}.",
        {"n": int(len(tmp)), "events": int(tmp[ev].sum())},
        "Kaplan–Meier estimates the survival function under independent censoring (censoring independent of failure risk given modelled covariates/groups). "
        "Median survival is the time at which estimated S(t) reaches 0.5; it may be undefined if fewer than half the sample fail.",
        tables={"medians": medians, "curve": to_native(curves_df.head(400))},
        n=int(len(tmp)),
    )


def logrank(df, params):
    from lifelines.statistics import multivariate_logrank_test

    dur = params.get("duration") or params.get("y")
    ev = params.get("event")
    g = params.get("group") or params.get("x")
    tmp = df[[dur, ev, g]].dropna()
    tmp[dur] = pd.to_numeric(tmp[dur], errors="coerce")
    tmp[ev] = pd.to_numeric(tmp[ev], errors="coerce")
    tmp = tmp.dropna()
    res = multivariate_logrank_test(tmp[dur], tmp[g], tmp[ev])
    return result(
        "logrank",
        "Log-rank test",
        f"Log-rank χ² = {float(res.test_statistic):.3f}, p = {p_format(res.p_value)}, df = {int(res.degrees_of_freedom)}.",
        {"chi2": float(res.test_statistic), "p_value": float(res.p_value), "df": int(res.degrees_of_freedom), "n": int(len(tmp))},
        f"The log-rank test compares survival curves across levels of '{g}'. χ²={float(res.test_statistic):.3f}, p={p_format(res.p_value)} ({sig_label(res.p_value)}). "
        "It is most powerful under proportional hazards.",
        n=int(len(tmp)),
    )


def cox_ph(df, params):
    from lifelines import CoxPHFitter

    dur = params.get("duration") or params.get("y")
    ev = params.get("event")
    xs = params.get("x") or params.get("predictors") or params.get("columns")
    if isinstance(xs, str):
        xs = [xs]
    cols = [dur, ev] + list(xs)
    tmp = df[cols].copy()
    for c in cols:
        tmp[c] = pd.to_numeric(tmp[c], errors="coerce")
    tmp = tmp.dropna()
    tmp = tmp.rename(columns={dur: "T", ev: "E"})
    cph = CoxPHFitter()
    cph.fit(tmp, duration_col="T", event_col="E")
    summ = cph.summary.reset_index()
    return result(
        "cox_ph",
        "Cox proportional hazards",
        f"Cox model for time '{dur}', event '{ev}'. Concordance={float(cph.concordance_index_):.3f}, n={int(cph.nobs)}.",
        {
            "n": int(cph._n_examples) if hasattr(cph, "_n_examples") else int(len(tmp)),
            "concordance": float(cph.concordance_index_),
            "neg_log_likelihood": float(cph.log_likelihood_),
        },
        "Cox PH models the hazard ratio associated with covariates, assuming proportional hazards and independent censoring. "
        "Hazard ratios are multiplicative associations, not necessarily causal. Check PH (Schoenfeld residuals) before interpreting a single HR as constant over time.",
        tables={"coefficients": to_native(summ)},
        n=int(len(tmp)),
        warnings=["Proportional-hazards assumption was not automatically verified in this run. Inspect Schoenfeld residual tests."],
        formula="h(t|X) = h0(t) exp(Xβ)",
    )


# ── Reliability ──────────────────────────────────────────────


def cronbach_alpha(df, params):
    cols = params.get("columns") or params.get("items")
    if not cols or len(cols) < 2:
        raise ValueError("Cronbach's alpha needs ≥ 2 item columns.")
    X = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    k = X.shape[1]
    item_var = X.var(axis=0, ddof=1)
    tot_var = X.sum(axis=1).var(ddof=1)
    alpha = float(k / (k - 1) * (1 - item_var.sum() / tot_var)) if tot_var else None
    # item-total
    total = X.sum(axis=1)
    items = []
    for c in cols:
        rest = total - X[c]
        r, p = stats.pearsonr(X[c], rest)
        items.append({"item": c, "item_total_r": float(r), "p_value": float(p), "mean": float(X[c].mean()), "sd": float(X[c].std(ddof=1))})
    interp = (
        "unacceptable"
        if alpha is None or alpha < 0.5
        else "poor"
        if alpha < 0.6
        else "questionable"
        if alpha < 0.7
        else "acceptable"
        if alpha < 0.8
        else "good"
        if alpha < 0.9
        else "excellent (or possibly redundant items)"
    )
    return result(
        "cronbach_alpha",
        "Cronbach's alpha",
        f"α = {alpha:.3f} ({interp}) for {k} items, n={len(X)}.",
        {"alpha": alpha, "n_items": k, "n": int(len(X))},
        f"Cronbach's α = {alpha:.3f}, conventionally {interp} internal consistency. "
        "α increases with the number of items and assumes tau-equivalence; it is not a measure of unidimensionality or validity.",
        tables={"item_total": items},
        n=int(len(X)),
        formula="α = k/(k−1) · (1 − Σσ²_i / σ²_total)",
    )


# ── Effect size / power ──────────────────────────────────────


def effect_size(df, params):
    kind = params.get("kind", "cohens_d")
    if kind in ("cohens_d", "hedges_g"):
        y, g = params.get("y"), params.get("x")
        groups = _groups(df, y, g, params.get("levels"))
        if len(groups) != 2:
            raise ValueError("Cohen's d needs two groups.")
        (_, a), (_, b) = list(groups.items())
        d = _cohens_d(a, b)
        gval = _hedges_g(d, len(a) + len(b))
        return result(
            "effect_size",
            "Standardized mean difference",
            f"Cohen's d = {d:.3f}, Hedges' g = {gval:.3f}.",
            {"cohens_d": d, "hedges_g": gval, "n_1": len(a), "n_2": len(b)},
            "Cohen's conventional benchmarks (0.2/0.5/0.8) are context-free heuristics, not scientific laws. Report the raw mean difference alongside d.",
            n=len(a) + len(b),
        )
    raise ValueError("Unsupported effect size kind")


def power_ttest(df, params):
    from statsmodels.stats.power import TTestIndPower

    d = float(params.get("d") or params.get("es") or 0.5)
    n = params.get("n")
    power = params.get("power")
    alpha = float(params.get("alpha", 0.05))
    analysis = TTestIndPower()
    if n and not power:
        n = int(n)
        pw = float(analysis.power(effect_size=d, nobs1=n, alpha=alpha, ratio=1.0))
        return result(
            "power_analysis",
            "Two-sample t-test power",
            f"Power = {pw:.3f} for d={d}, n/group={n}, α={alpha}.",
            {"power": pw, "d": d, "n_per_group": n, "alpha": alpha},
            f"Estimated power to detect d={d} with n={n} per group at α={alpha} is {pw:.3f}. "
            "Power calculations are only as honest as the assumed effect size.",
        )
    pw = float(params.get("power", 0.8))
    nreq = float(analysis.solve_power(effect_size=d, power=pw, alpha=alpha, ratio=1.0))
    return result(
        "sample_size",
        "Sample size (two-sample t)",
        f"n ≈ {nreq:.1f} per group for d={d}, power={pw}, α={alpha}.",
        {"n_per_group": nreq, "d": d, "power": pw, "alpha": alpha},
        f"To detect d={d} with power {pw} at α={alpha} in a two-sample t-test, you need about {int(np.ceil(nreq))} observations per group (equal n, two-sided).",
    )


def levene_test(df, params):
    y, g = params.get("y"), params.get("x") or params.get("group")
    groups = _groups(df, y, g, params.get("levels"))
    W, p = stats.levene(*groups.values())
    return result(
        "levene",
        "Levene's test (homogeneity of variance)",
        f"W = {W:.3f}, p = {p_format(p)}.",
        {"W": float(W), "p_value": float(p), "k": len(groups)},
        f"Levene's test of equal variances across '{g}'. W={W:.3f}, p={p_format(p)}. "
        + ("Variances appear heterogeneous; prefer Welch procedures or rank tests." if p < 0.05 else "No significant evidence of variance heterogeneity at α=0.05."),
        n=sum(len(v) for v in groups.values()),
    )


# ── Dispatcher ───────────────────────────────────────────────

REGISTRY: dict[str, Callable] = {
    "descriptive": descriptive,
    "frequency": frequency,
    "shapiro_wilk": shapiro_wilk,
    "anderson_darling": anderson_darling,
    "kolmogorov_smirnov": ks_normal,
    "pearson": pearson,
    "spearman": spearman,
    "kendall": kendall,
    "correlation_matrix": correlation_matrix,
    "chi_square": chi_square,
    "fisher_exact": fisher_exact,
    "cramers_v": cramers_v,
    "one_sample_t": one_sample_t,
    "independent_t": independent_t,
    "paired_t": paired_t,
    "z_test": z_test,
    "mannwhitney": mannwhitney,
    "wilcoxon": wilcoxon,
    "kruskal": kruskal,
    "friedman": friedman,
    "oneway_anova": oneway_anova,
    "twoway_anova": twoway_anova,
    "repeated_anova": repeated_anova,
    "ancova": ancova,
    "tukey_hsd": tukey_hsd,
    "linear_regression": linear_regression,
    "multiple_regression": linear_regression,
    "polynomial_regression": polynomial_regression,
    "logistic_regression": logistic_regression,
    "poisson_regression": poisson_regression,
    "negative_binomial": negative_binomial,
    "robust_regression": robust_regression,
    "trend_analysis": trend_analysis,
    "moving_average": moving_average,
    "acf_pacf": acf_pacf,
    "arima": arima_model,
    "sarima": sarima_model,
    "exp_smoothing": exp_smoothing,
    "seasonality": seasonality,
    "pca": pca_analysis,
    "factor_analysis": factor_analysis,
    "manova": manova,
    "kmeans": kmeans_cluster,
    "lda": lda_analysis,
    "bootstrap_ci": bootstrap_ci,
    "permutation_test": permutation_test,
    "kaplan_meier": kaplan_meier,
    "logrank": logrank,
    "cox_ph": cox_ph,
    "cronbach_alpha": cronbach_alpha,
    "effect_size": effect_size,
    "power_analysis": power_ttest,
    "sample_size": power_ttest,
    "levene": levene_test,
}


METHOD_META = [
    {"id": "descriptive", "label": "Descriptive statistics", "family": "Descriptive", "needs": ["columns?"]},
    {"id": "frequency", "label": "Frequency table", "family": "Descriptive", "needs": ["column"]},
    {"id": "shapiro_wilk", "label": "Shapiro–Wilk", "family": "Normality", "needs": ["column"]},
    {"id": "anderson_darling", "label": "Anderson–Darling", "family": "Normality", "needs": ["column"]},
    {"id": "kolmogorov_smirnov", "label": "Kolmogorov–Smirnov", "family": "Normality", "needs": ["column"]},
    {"id": "pearson", "label": "Pearson correlation", "family": "Correlation", "needs": ["x", "y"]},
    {"id": "spearman", "label": "Spearman correlation", "family": "Correlation", "needs": ["x", "y"]},
    {"id": "kendall", "label": "Kendall's tau", "family": "Correlation", "needs": ["x", "y"]},
    {"id": "correlation_matrix", "label": "Correlation matrix", "family": "Correlation", "needs": ["columns?"]},
    {"id": "chi_square", "label": "Chi-square test", "family": "Association", "needs": ["x", "y"]},
    {"id": "fisher_exact", "label": "Fisher's exact test", "family": "Association", "needs": ["x", "y"]},
    {"id": "cramers_v", "label": "Cramér's V", "family": "Association", "needs": ["x", "y"]},
    {"id": "one_sample_t", "label": "One-sample t-test", "family": "Hypothesis testing", "needs": ["y", "mu?"]},
    {"id": "independent_t", "label": "Independent t-test", "family": "Hypothesis testing", "needs": ["y", "x"]},
    {"id": "paired_t", "label": "Paired t-test", "family": "Hypothesis testing", "needs": ["y", "x"]},
    {"id": "z_test", "label": "z-test", "family": "Hypothesis testing", "needs": ["y", "mu?"]},
    {"id": "mannwhitney", "label": "Mann–Whitney U", "family": "Hypothesis testing", "needs": ["y", "x"]},
    {"id": "wilcoxon", "label": "Wilcoxon signed-rank", "family": "Hypothesis testing", "needs": ["y", "x"]},
    {"id": "kruskal", "label": "Kruskal–Wallis", "family": "Hypothesis testing", "needs": ["y", "x"]},
    {"id": "friedman", "label": "Friedman test", "family": "Hypothesis testing", "needs": ["columns"]},
    {"id": "oneway_anova", "label": "One-way ANOVA", "family": "ANOVA", "needs": ["y", "x"]},
    {"id": "twoway_anova", "label": "Two-way ANOVA", "family": "ANOVA", "needs": ["y", "factor1", "factor2"]},
    {"id": "repeated_anova", "label": "Repeated-measures ANOVA", "family": "ANOVA", "needs": ["columns"]},
    {"id": "ancova", "label": "ANCOVA", "family": "ANOVA", "needs": ["y", "x", "covariate"]},
    {"id": "tukey_hsd", "label": "Tukey HSD", "family": "ANOVA", "needs": ["y", "x"]},
    {"id": "linear_regression", "label": "Simple linear regression", "family": "Regression", "needs": ["y", "x"]},
    {"id": "multiple_regression", "label": "Multiple linear regression", "family": "Regression", "needs": ["y", "x"]},
    {"id": "polynomial_regression", "label": "Polynomial regression", "family": "Regression", "needs": ["y", "x", "degree?"]},
    {"id": "logistic_regression", "label": "Logistic regression", "family": "Regression", "needs": ["y", "x"]},
    {"id": "poisson_regression", "label": "Poisson regression", "family": "Regression", "needs": ["y", "x"]},
    {"id": "negative_binomial", "label": "Negative binomial regression", "family": "Regression", "needs": ["y", "x"]},
    {"id": "robust_regression", "label": "Robust regression (HC3)", "family": "Regression", "needs": ["y", "x"]},
    {"id": "trend_analysis", "label": "Linear trend", "family": "Time series", "needs": ["y", "time?"]},
    {"id": "moving_average", "label": "Moving average", "family": "Time series", "needs": ["y", "window?"]},
    {"id": "acf_pacf", "label": "ACF / PACF", "family": "Time series", "needs": ["y"]},
    {"id": "arima", "label": "ARIMA", "family": "Time series", "needs": ["y"]},
    {"id": "sarima", "label": "SARIMA", "family": "Time series", "needs": ["y"]},
    {"id": "exp_smoothing", "label": "Exponential smoothing", "family": "Time series", "needs": ["y"]},
    {"id": "seasonality", "label": "Seasonality profile", "family": "Time series", "needs": ["y", "period?"]},
    {"id": "pca", "label": "PCA", "family": "Multivariate", "needs": ["columns?"]},
    {"id": "factor_analysis", "label": "Factor analysis", "family": "Multivariate", "needs": ["columns?"]},
    {"id": "manova", "label": "MANOVA", "family": "Multivariate", "needs": ["dvs", "group"]},
    {"id": "kmeans", "label": "K-means clustering", "family": "Multivariate", "needs": ["columns?", "k?"]},
    {"id": "lda", "label": "Discriminant analysis", "family": "Multivariate", "needs": ["y", "columns?"]},
    {"id": "bootstrap_ci", "label": "Bootstrap CI", "family": "Nonparametric", "needs": ["column"]},
    {"id": "permutation_test", "label": "Permutation test", "family": "Nonparametric", "needs": ["y", "x"]},
    {"id": "kaplan_meier", "label": "Kaplan–Meier", "family": "Survival", "needs": ["duration", "event"]},
    {"id": "logrank", "label": "Log-rank test", "family": "Survival", "needs": ["duration", "event", "group"]},
    {"id": "cox_ph", "label": "Cox PH model", "family": "Survival", "needs": ["duration", "event", "x"]},
    {"id": "cronbach_alpha", "label": "Cronbach's alpha", "family": "Reliability", "needs": ["columns"]},
    {"id": "effect_size", "label": "Effect size (d / g)", "family": "Experimental", "needs": ["y", "x"]},
    {"id": "power_analysis", "label": "Power analysis", "family": "Experimental", "needs": ["d?", "n?"]},
    {"id": "sample_size", "label": "Sample size estimation", "family": "Experimental", "needs": ["d?", "power?"]},
    {"id": "levene", "label": "Levene's test", "family": "Assumptions", "needs": ["y", "x"]},
]


def run_method(df: pd.DataFrame, method: str, params: dict) -> dict:
    fn = REGISTRY.get(method)
    if not fn:
        raise ValueError(f"Unknown method '{method}'.")
    return fn(df, params or {})
