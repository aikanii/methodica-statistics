from __future__ import annotations

import pandas as pd
import numpy as np

from ..utils import to_native
from .types import classify_series, column_roles


NEGATIVE_UNFRIENDLY = {
    "age",
    "count",
    "qty",
    "quantity",
    "price",
    "amount",
    "weight",
    "height",
    "duration",
    "pm2.5",
    "pm25",
    "pm10",
    "humidity",
    "rainfall",
    "population",
    "score",
    "rating",
}


def assess_quality(df: pd.DataFrame) -> dict:
    issues = []
    roles = column_roles(df)

    # missing
    for col in df.columns:
        n = int(df[col].isna().sum())
        if n:
            pct = 100 * n / max(len(df), 1)
            sev = "high" if pct >= 30 else "medium" if pct >= 5 else "low"
            issues.append(
                _issue(
                    "missing_values",
                    col,
                    sev,
                    f"{n} missing values ({pct:.1f}%) in '{col}'.",
                    "Missing data can bias estimates if the mechanism is not MCAR.",
                    "Impute with an appropriate method or drop rows/columns after reviewing the missingness pattern.",
                    preview={"n_missing": n, "pct": round(pct, 2)},
                    proposed={"operation": "impute", "column": col, "method": "median" if roles[col] == "numeric" else "mode"},
                )
            )

    # duplicate rows
    dups = int(df.duplicated().sum())
    if dups:
        issues.append(
            _issue(
                "duplicate_rows",
                None,
                "medium" if dups / max(len(df), 1) < 0.05 else "high",
                f"{dups} duplicate rows detected.",
                "Exact duplicate records inflate sample size and can distort p-values.",
                "Remove duplicate rows, keeping the first occurrence.",
                preview={"n": dups, "examples": to_native(df[df.duplicated(keep=False)].head(5))},
                proposed={"operation": "drop_duplicates"},
            )
        )

    # duplicate columns
    seen = {}
    for col in df.columns:
        key = tuple(df[col].astype(str).fillna("__NA__").tolist()[:5000]) if len(df) else tuple()
        # hash-like: use values equality vs previous columns
    for i, c1 in enumerate(df.columns):
        for c2 in list(df.columns)[i + 1 :]:
            try:
                if df[c1].equals(df[c2]):
                    issues.append(
                        _issue(
                            "duplicate_columns",
                            f"{c1} / {c2}",
                            "medium",
                            f"Columns '{c1}' and '{c2}' are identical.",
                            "Duplicate features add no information and can inflate multicollinearity.",
                            f"Drop column '{c2}'.",
                            proposed={"operation": "drop_columns", "columns": [c2]},
                        )
                    )
            except Exception:
                pass

    for col, role in roles.items():
        s = df[col]
        # constant
        if s.nunique(dropna=True) <= 1:
            issues.append(
                _issue(
                    "constant_variable",
                    col,
                    "medium",
                    f"'{col}' is constant (no variation).",
                    "A constant variable cannot explain variance or be used as a predictor.",
                    f"Drop column '{col}' unless it is a study identifier you wish to keep.",
                    proposed={"operation": "drop_columns", "columns": [col]},
                )
            )

        # high cardinality
        nunq = s.nunique(dropna=True)
        if role in ("categorical", "text") and nunq > 100 and nunq > 0.4 * max(len(df), 1):
            issues.append(
                _issue(
                    "high_cardinality",
                    col,
                    "low",
                    f"'{col}' has {nunq} distinct values.",
                    "High-cardinality categoricals produce sparse dummy variables and unstable estimates.",
                    "Treat as identifier, group rare levels, or exclude from modeling.",
                )
            )

        if role == "numeric":
            num = pd.to_numeric(s, errors="coerce")
            # mixed / invalid types
            n_invalid = int(s.notna().sum() - num.notna().sum())
            if n_invalid:
                issues.append(
                    _issue(
                        "invalid_data_type",
                        col,
                        "high",
                        f"{n_invalid} non-numeric values in numeric-like column '{col}'.",
                        "Type inconsistencies usually indicate data-entry errors.",
                        "Coerce to numeric (invalid entries become missing) after reviewing them.",
                        preview={"examples": to_native(s[num.isna() & s.notna()].head(8).tolist())},
                        proposed={"operation": "to_numeric", "column": col},
                    )
                )

            # outliers IQR
            q1, q3 = num.quantile(0.25), num.quantile(0.75)
            iqr = q3 - q1
            if pd.notna(iqr) and iqr > 0:
                mask = (num < q1 - 1.5 * iqr) | (num > q3 + 1.5 * iqr)
                n_out = int(mask.sum())
                if n_out:
                    sev = "low" if n_out / max(num.notna().sum(), 1) < 0.05 else "medium"
                    issues.append(
                        _issue(
                            "outliers",
                            col,
                            sev,
                            f"{n_out} IQR outliers in '{col}'.",
                            "Outliers can distort means, variances, and parametric tests. They may be genuine extremes.",
                            "Inspect values. Options: keep, winsorize, transform, or exclude with justification.",
                            preview={
                                "n": n_out,
                                "bounds": [to_native(q1 - 1.5 * iqr), to_native(q3 + 1.5 * iqr)],
                                "examples": to_native(num[mask].head(8).tolist()),
                            },
                            proposed={"operation": "winsorize", "column": col, "limits": 0.01},
                        )
                    )
                # extreme 3 IQR
                mask3 = (num < q1 - 3 * iqr) | (num > q3 + 3 * iqr)
                n3 = int(mask3.sum())
                if n3:
                    issues.append(
                        _issue(
                            "extreme_values",
                            col,
                            "medium",
                            f"{n3} extreme values (> 3×IQR) in '{col}'.",
                            "Values this far from the bulk of the distribution are often errors or a different population.",
                            "Review source data before excluding or transforming.",
                            preview={"examples": to_native(num[mask3].head(8).tolist())},
                        )
                    )

            # negative where inappropriate
            key = str(col).lower().replace(" ", "")
            if any(k.replace(".", "") in key or k in str(col).lower() for k in NEGATIVE_UNFRIENDLY):
                nneg = int((num < 0).sum())
                if nneg:
                    issues.append(
                        _issue(
                            "impossible_values",
                            col,
                            "high",
                            f"{nneg} negative values in '{col}', which is typically non-negative.",
                            "Impossible values indicate measurement or coding errors.",
                            "Set negatives to missing or correct from source.",
                            preview={"examples": to_native(num[num < 0].head(8).tolist())},
                            proposed={"operation": "clip_nonnegative", "column": col},
                        )
                    )

        if role == "datetime":
            dt = pd.to_datetime(s, errors="coerce")
            n_invalid = int(s.notna().sum() - dt.notna().sum())
            if n_invalid:
                issues.append(
                    _issue(
                        "invalid_dates",
                        col,
                        "high",
                        f"{n_invalid} values in '{col}' are not valid dates.",
                        "Invalid dates break time-series analyses and duration calculations.",
                        "Parse with an explicit format; unparsable values become missing.",
                        proposed={"operation": "parse_dates", "column": col},
                    )
                )
            if dt.notna().any():
                future = dt > (pd.Timestamp.utcnow().tz_localize(None) + pd.Timedelta(days=1))
                nfut = int(future.fillna(False).sum())
                if nfut:
                    issues.append(
                        _issue(
                            "impossible_values",
                            col,
                            "medium",
                            f"{nfut} dates in '{col}' are in the future.",
                            "Future event dates may be data-entry errors unless the study is prospective.",
                            "Verify against the study protocol.",
                        )
                    )

        if role in ("categorical", "text"):
            vals = s.dropna().astype(str)
            stripped = vals.str.strip()
            n_ws = int((vals != stripped).sum())
            if n_ws:
                issues.append(
                    _issue(
                        "inconsistent_categories",
                        col,
                        "low",
                        f"{n_ws} values in '{col}' have extra whitespace.",
                        "Whitespace differences split a single category into several levels.",
                        "Trim whitespace.",
                        proposed={"operation": "strip", "column": col},
                    )
                )
            lower = vals.str.lower()
            if lower.nunique() < vals.nunique():
                issues.append(
                    _issue(
                        "inconsistent_categories",
                        col,
                        "medium",
                        f"'{col}' has case variants of the same label (e.g. 'Urban' vs 'urban').",
                        "Inconsistent capitalization splits groups and reduces power.",
                        "Standardize to a consistent case.",
                        proposed={"operation": "normalize_case", "column": col},
                    )
                )
            # near-duplicates via simple ratio
            uniq = list(vals.value_counts().head(40).index)
            near = []
            for i, a in enumerate(uniq):
                for b in uniq[i + 1 :]:
                    if a.lower() != b.lower() and _similar(a, b):
                        near.append((a, b))
            if near:
                issues.append(
                    _issue(
                        "potential_data_entry_errors",
                        col,
                        "low",
                        f"Possible misspellings in '{col}': " + ", ".join(f"{a} ≈ {b}" for a, b in near[:6]),
                        "Near-duplicate labels often come from typos.",
                        "Map aliases to a canonical label.",
                        preview={"pairs": near[:10]},
                    )
                )

    # summary
    sev_score = {"low": 1, "medium": 3, "high": 6}
    penalty = sum(sev_score.get(i["severity"], 1) for i in issues)
    score = round(max(0, 100 - penalty), 1)
    counts = {
        "high": sum(1 for i in issues if i["severity"] == "high"),
        "medium": sum(1 for i in issues if i["severity"] == "medium"),
        "low": sum(1 for i in issues if i["severity"] == "low"),
        "total": len(issues),
    }
    return {"score": score, "counts": counts, "issues": issues}


def _similar(a: str, b: str) -> bool:
    a, b = a.lower().strip(), b.lower().strip()
    if not a or not b:
        return False
    if abs(len(a) - len(b)) > 2:
        return False
    # simple edit distance bound
    if a in b or b in a:
        return abs(len(a) - len(b)) == 1
    diffs = sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))
    return 0 < diffs <= 2


def _issue(kind, location, severity, problem, explanation, suggestion, preview=None, proposed=None):
    return {
        "id": f"{kind}:{location or '*'}",
        "kind": kind,
        "location": location,
        "severity": severity,
        "problem": problem,
        "explanation": explanation,
        "suggestion": suggestion,
        "preview": preview,
        "proposed": proposed,
    }
