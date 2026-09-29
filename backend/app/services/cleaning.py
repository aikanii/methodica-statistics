from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def apply_operation(df: pd.DataFrame, op: dict) -> tuple[pd.DataFrame, str]:
    """Apply a single cleaning operation. Never run silently — caller records history."""
    name = op.get("operation")
    fn = OPERATIONS.get(name)
    if not fn:
        raise ValueError(f"Unknown cleaning operation: {name}")
    return fn(df.copy(), op)


def drop_duplicates(df, op):
    n = int(df.duplicated().sum())
    return df.drop_duplicates().reset_index(drop=True), f"Removed {n} duplicate rows"


def drop_columns(df, op):
    cols = [c for c in op.get("columns", []) if c in df.columns]
    return df.drop(columns=cols), f"Dropped columns: {', '.join(cols)}"


def drop_rows_missing(df, op):
    subset = op.get("columns") or None
    before = len(df)
    out = df.dropna(subset=subset)
    return out.reset_index(drop=True), f"Removed {before - len(out)} rows with missing values"


def impute(df, op):
    col = op["column"]
    method = op.get("method", "median")
    if col not in df.columns:
        raise ValueError(f"Column {col} not found")
    s = df[col]
    n = int(s.isna().sum())
    if method == "mean":
        val = pd.to_numeric(s, errors="coerce").mean()
        df[col] = s.fillna(val)
    elif method == "median":
        val = pd.to_numeric(s, errors="coerce").median()
        df[col] = s.fillna(val)
    elif method == "mode":
        mode = s.mode(dropna=True)
        val = mode.iloc[0] if len(mode) else None
        df[col] = s.fillna(val)
    elif method == "ffill":
        df[col] = s.ffill()
    elif method == "bfill":
        df[col] = s.bfill()
    elif method == "constant":
        df[col] = s.fillna(op.get("value"))
    elif method == "interpolate":
        df[col] = pd.to_numeric(s, errors="coerce").interpolate()
    elif method == "knn":
        from sklearn.impute import KNNImputer

        num = df.select_dtypes(include=[np.number])
        if col not in num.columns:
            raise ValueError("KNN imputation requires a numeric column")
        imp = KNNImputer(n_neighbors=int(op.get("k", 5)))
        filled = imp.fit_transform(num)
        df[col] = filled[:, list(num.columns).index(col)]
    elif method == "iterative":
        from sklearn.experimental import enable_iterative_imputer  # noqa: F401
        from sklearn.impute import IterativeImputer

        num = df.select_dtypes(include=[np.number])
        if col not in num.columns:
            raise ValueError("Iterative imputation requires a numeric column")
        imp = IterativeImputer(max_iter=10, random_state=0)
        filled = imp.fit_transform(num)
        df[col] = filled[:, list(num.columns).index(col)]
    else:
        raise ValueError(f"Unknown imputation method {method}")
    return df, f"Imputed {n} values in '{col}' using {method}"


def to_numeric(df, op):
    col = op["column"]
    df[col] = pd.to_numeric(df[col], errors="coerce")
    return df, f"Coerced '{col}' to numeric"


def parse_dates(df, op):
    col = op["column"]
    df[col] = pd.to_datetime(df[col], errors="coerce")
    return df, f"Parsed '{col}' as datetime"


def strip_col(df, op):
    col = op["column"]
    df[col] = df[col].astype(str).where(df[col].notna(), other=np.nan)
    df[col] = df[col].str.strip()
    return df, f"Trimmed whitespace in '{col}'"


def normalize_case(df, op):
    col = op["column"]
    how = op.get("case", "title")
    s = df[col].astype(str).where(df[col].notna(), other=np.nan)
    if how == "lower":
        df[col] = s.str.lower()
    elif how == "upper":
        df[col] = s.str.upper()
    else:
        df[col] = s.str.strip().str.title()
    return df, f"Normalized case in '{col}'"


def winsorize(df, op):
    col = op["column"]
    limits = float(op.get("limits", 0.01))
    num = pd.to_numeric(df[col], errors="coerce")
    lo, hi = num.quantile(limits), num.quantile(1 - limits)
    df[col] = num.clip(lo, hi)
    return df, f"Winsorized '{col}' at {limits:.2%} tails"


def clip_nonnegative(df, op):
    col = op["column"]
    num = pd.to_numeric(df[col], errors="coerce")
    n = int((num < 0).sum())
    df[col] = num.mask(num < 0, np.nan)
    return df, f"Set {n} negative values in '{col}' to missing"


def transform(df, op):
    col = op["column"]
    how = op.get("method", "log")
    num = pd.to_numeric(df[col], errors="coerce")
    if how == "log":
        df[col + "_log"] = np.log(num.where(num > 0))
        msg = f"Created log({col}) as {col}_log (undefined for ≤ 0)"
    elif how == "log1p":
        df[col + "_log1p"] = np.log1p(num.clip(lower=0))
        msg = f"Created log1p({col})"
    elif how == "sqrt":
        df[col + "_sqrt"] = np.sqrt(num.clip(lower=0))
        msg = f"Created sqrt({col})"
    elif how == "zscore":
        df[col + "_z"] = (num - num.mean()) / num.std(ddof=1)
        msg = f"Created z-score of {col}"
    elif how == "minmax":
        df[col + "_minmax"] = (num - num.min()) / (num.max() - num.min())
        msg = f"Created min-max scaled {col}"
    else:
        raise ValueError(how)
    return df, msg


def encode(df, op):
    col = op["column"]
    how = op.get("method", "onehot")
    if how == "onehot":
        dummies = pd.get_dummies(df[col], prefix=col, dummy_na=False)
        df = pd.concat([df, dummies], axis=1)
        return df, f"One-hot encoded '{col}' ({dummies.shape[1]} columns)"
    if how == "label":
        cats = {v: i for i, v in enumerate(df[col].dropna().unique())}
        df[col + "_code"] = df[col].map(cats)
        return df, f"Label-encoded '{col}'"
    raise ValueError(how)


def rename_column(df, op):
    df = df.rename(columns={op["column"]: op["new_name"]})
    return df, f"Renamed {op['column']} → {op['new_name']}"


def filter_rows(df, op):
    expr = op.get("query")
    before = len(df)
    out = df.query(expr, engine="python")
    return out.reset_index(drop=True), f"Filtered with `{expr}` ({before} → {len(out)} rows)"


def fill_missing_all(df, op):
    strategy = op.get("method", "auto")
    msgs = []
    for col in df.columns:
        if df[col].isna().sum() == 0:
            continue
        if pd.api.types.is_numeric_dtype(df[col]) and strategy in ("auto", "median", "mean"):
            m = "median" if strategy == "auto" else strategy
            df, msg = impute(df, {"column": col, "method": m})
        else:
            df, msg = impute(df, {"column": col, "method": "mode"})
        msgs.append(msg)
    return df, "; ".join(msgs) or "No missing values"


OPERATIONS = {
    "drop_duplicates": drop_duplicates,
    "drop_columns": drop_columns,
    "drop_rows_missing": drop_rows_missing,
    "impute": impute,
    "to_numeric": to_numeric,
    "parse_dates": parse_dates,
    "strip": strip_col,
    "normalize_case": normalize_case,
    "winsorize": winsorize,
    "clip_nonnegative": clip_nonnegative,
    "transform": transform,
    "encode": encode,
    "rename": rename_column,
    "filter": filter_rows,
    "impute_all": fill_missing_all,
}


def propose_from_quality(issues: list[dict]) -> list[dict]:
    seen = set()
    ops = []
    for iss in issues:
        p = iss.get("proposed")
        if not p:
            continue
        key = tuple(sorted((k, str(v)) for k, v in p.items()))
        if key in seen:
            continue
        seen.add(key)
        ops.append({**p, "from_issue": iss["id"], "severity": iss["severity"], "problem": iss["problem"]})
    return ops
