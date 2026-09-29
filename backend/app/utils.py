from __future__ import annotations

import math
import re
import uuid
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd


def new_id() -> str:
    return uuid.uuid4().hex


def to_native(obj: Any) -> Any:
    """Recursively convert numpy/pandas objects into JSON-safe Python types."""
    if obj is None:
        return None
    if isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(obj, (np.ndarray,)):
        return [to_native(x) for x in obj.tolist()]
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, pd.Timedelta):
        return str(obj)
    if isinstance(obj, (pd.Series,)):
        return [to_native(x) for x in obj.tolist()]
    if isinstance(obj, pd.DataFrame):
        return df_records(obj)
    if isinstance(obj, dict):
        return {str(k): to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_native(x) for x in obj]
    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass
    return str(obj)


def df_records(df: pd.DataFrame, limit: int | None = None) -> list[dict]:
    if limit is not None:
        df = df.head(limit)
    out = []
    for rec in df.to_dict(orient="records"):
        out.append({str(k): to_native(v) for k, v in rec.items()})
    return out


def safe_float(x, default=None):
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except Exception:
        return default


def p_format(p) -> str:
    p = safe_float(p)
    if p is None:
        return "n/a"
    if p < 0.0001:
        return f"{p:.2e}"
    return f"{p:.4f}"


def sig_label(p, alpha=0.05) -> str:
    p = safe_float(p)
    if p is None:
        return "undetermined"
    if p < 0.001:
        return "highly significant (p < 0.001)"
    if p < 0.01:
        return "significant (p < 0.01)"
    if p < alpha:
        return f"significant (p < {alpha})"
    return f"not significant (p ≥ {alpha})"


def slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", str(s).strip().lower())
    return s.strip("-")[:80] or "item"


def memory_usage_str(df: pd.DataFrame) -> str:
    n = int(df.memory_usage(deep=True).sum())
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n/1024:.1f} KB"
    if n < 1024**3:
        return f"{n/1024**2:.2f} MB"
    return f"{n/1024**3:.2f} GB"


def is_id_like(name: str, series: pd.Series) -> bool:
    n = name.lower()
    if re.search(r"(^id$|_id$|uuid|guid|patient.?id|record.?id|row.?id)", n):
        return True
    if series.dtype == object:
        nunq = series.nunique(dropna=True)
        if len(series) > 20 and nunq == series.notna().sum() and nunq == len(series):
            return True
    return False
