from __future__ import annotations

import pandas as pd
import numpy as np


def classify_series(s: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "datetime"
    if pd.api.types.is_numeric_dtype(s):
        nunq = s.nunique(dropna=True)
        if nunq <= 2 and set(s.dropna().unique()).issubset({0, 1, 0.0, 1.0}):
            return "boolean"
        return "numeric"
    # object
    nunq = s.nunique(dropna=True)
    n = s.notna().sum()
    if nunq <= 2:
        vals = set(str(x).lower() for x in s.dropna().unique())
        if vals <= {"true", "false", "yes", "no", "y", "n", "0", "1", "t", "f"}:
            return "boolean"
    # try datetime
    if n > 0:
        sample = s.dropna().astype(str).head(40)
        parsed = pd.to_datetime(sample, errors="coerce")
        if parsed.notna().mean() > 0.85:
            return "datetime"
    if nunq == 0:
        return "empty"
    if n > 0 and nunq / max(n, 1) < 0.08 and nunq <= 50:
        return "categorical"
    if nunq <= 20:
        return "categorical"
    return "text"


def column_roles(df: pd.DataFrame) -> dict[str, str]:
    return {c: classify_series(df[c]) for c in df.columns}


def numeric_cols(df: pd.DataFrame) -> list[str]:
    return [c for c, t in column_roles(df).items() if t == "numeric"]


def categorical_cols(df: pd.DataFrame) -> list[str]:
    return [c for c, t in column_roles(df).items() if t in ("categorical", "boolean")]


def datetime_cols(df: pd.DataFrame) -> list[str]:
    return [c for c, t in column_roles(df).items() if t == "datetime"]
