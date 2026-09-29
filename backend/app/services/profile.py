from __future__ import annotations

import pandas as pd
import numpy as np

from ..utils import is_id_like, memory_usage_str, to_native
from .types import classify_series, column_roles


def profile_dataset(df: pd.DataFrame) -> dict:
    roles = column_roles(df)
    n_rows, n_cols = int(df.shape[0]), int(df.shape[1])
    missing_cells = int(df.isna().sum().sum())
    total_cells = max(n_rows * n_cols, 1)
    dup_rows = int(df.duplicated().sum())
    columns = [profile_column(df, c, roles[c]) for c in df.columns]
    id_cols = [c for c in df.columns if is_id_like(c, df[c])]
    const_cols = [c["name"] for c in columns if c["n_unique"] <= 1]
    high_card = [
        c["name"]
        for c in columns
        if c["role"] in ("categorical", "text") and c["n_unique"] > min(100, max(20, n_rows * 0.5))
    ]
    quality_score = compute_quality_score(df, missing_cells / total_cells, dup_rows, const_cols)
    return {
        "n_rows": n_rows,
        "n_cols": n_cols,
        "memory": memory_usage_str(df),
        "missing_cells": missing_cells,
        "missing_pct": round(100 * missing_cells / total_cells, 2),
        "duplicate_rows": dup_rows,
        "duplicate_pct": round(100 * dup_rows / max(n_rows, 1), 2),
        "id_columns": id_cols,
        "constant_columns": const_cols,
        "high_cardinality_columns": high_card,
        "type_counts": {
            "numeric": sum(1 for r in roles.values() if r == "numeric"),
            "categorical": sum(1 for r in roles.values() if r == "categorical"),
            "datetime": sum(1 for r in roles.values() if r == "datetime"),
            "boolean": sum(1 for r in roles.values() if r == "boolean"),
            "text": sum(1 for r in roles.values() if r == "text"),
        },
        "quality_score": quality_score,
        "columns": columns,
        "roles": roles,
    }


def profile_column(df: pd.DataFrame, name: str, role: str | None = None) -> dict:
    s = df[name]
    role = role or classify_series(s)
    n = len(s)
    n_missing = int(s.isna().sum())
    n_unique = int(s.nunique(dropna=True))
    info = {
        "name": str(name),
        "role": role,
        "dtype": str(s.dtype),
        "n": n,
        "n_missing": n_missing,
        "missing_pct": round(100 * n_missing / max(n, 1), 2),
        "n_unique": n_unique,
        "unique_pct": round(100 * n_unique / max(n - n_missing, 1), 2),
        "example_values": to_native(list(s.dropna().astype(str).head(8))),
        "is_constant": n_unique <= 1,
        "is_id_like": is_id_like(str(name), s),
    }
    if role == "numeric":
        num = pd.to_numeric(s, errors="coerce")
        desc = num.describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
        info.update(
            {
                "mean": to_native(num.mean()),
                "median": to_native(num.median()),
                "std": to_native(num.std()),
                "min": to_native(num.min()),
                "max": to_native(num.max()),
                "q1": to_native(num.quantile(0.25)),
                "q3": to_native(num.quantile(0.75)),
                "iqr": to_native(num.quantile(0.75) - num.quantile(0.25)),
                "skewness": to_native(num.skew()),
                "kurtosis": to_native(num.kurtosis()),
                "zeros": int((num == 0).sum()),
                "negatives": int((num < 0).sum()),
                "percentiles": {str(k): to_native(v) for k, v in desc.items()},
            }
        )
    elif role in ("categorical", "boolean", "text"):
        vc = s.astype(str).where(s.notna(), other=None)
        vc = s.dropna().astype(str).value_counts().head(12)
        info["top_values"] = [{"value": str(i), "count": int(c)} for i, c in vc.items()]
    elif role == "datetime":
        dt = pd.to_datetime(s, errors="coerce")
        info.update(
            {
                "min": to_native(dt.min()),
                "max": to_native(dt.max()),
                "n_invalid": int(s.notna().sum() - dt.notna().sum()),
            }
        )
    return info


def compute_quality_score(df: pd.DataFrame, miss_frac: float, dup_rows: int, const_cols: list) -> float:
    score = 100.0
    score -= min(40.0, miss_frac * 100 * 1.2)
    score -= min(20.0, 100 * dup_rows / max(len(df), 1))
    score -= min(15.0, 5 * len(const_cols))
    # mixed type penalty
    for c in df.columns:
        if df[c].dtype == object:
            sample = df[c].dropna().head(200)
            if len(sample) > 10:
                numish = pd.to_numeric(sample, errors="coerce").notna().mean()
                if 0.15 < numish < 0.85:
                    score -= 3
    return round(max(0, min(100, score)), 1)
