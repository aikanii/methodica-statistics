from __future__ import annotations

import pandas as pd
import numpy as np
from scipy import stats

from ..utils import df_records, to_native
from .profile import profile_column
from .types import column_roles
from .visualize import auto_eda_charts, build_chart


def explore(df: pd.DataFrame, params: dict | None = None) -> dict:
    params = params or {}
    roles = column_roles(df)
    nums = [c for c, r in roles.items() if r == "numeric"]
    cats = [c for c, r in roles.items() if r in ("categorical", "boolean")]

    desc_rows = []
    for c in nums:
        desc_rows.append(profile_column(df, c, "numeric"))

    freq = {}
    for c in cats[:12]:
        vc = df[c].dropna().astype(str).value_counts().head(20)
        n = int(vc.sum())
        freq[c] = [{"level": str(i), "count": int(v), "percent": round(100 * v / max(n, 1), 2)} for i, v in vc.items()]

    corr = None
    if len(nums) >= 2:
        sub = df[nums].apply(pd.to_numeric, errors="coerce")
        corr = to_native(sub.corr().reset_index().rename(columns={"index": "variable"}))

    charts = auto_eda_charts(df)

    return {
        "roles": roles,
        "descriptives": desc_rows,
        "frequencies": freq,
        "correlation": corr,
        "charts": charts,
        "n_rows": int(len(df)),
        "n_cols": int(df.shape[1]),
    }


def group_compare(df: pd.DataFrame, y: str, g: str) -> dict:
    tmp = df[[y, g]].dropna()
    tmp[y] = pd.to_numeric(tmp[y], errors="coerce")
    tmp = tmp.dropna()
    rows = []
    for name, part in tmp.groupby(g):
        x = part[y]
        rows.append(
            {
                "group": str(name),
                "n": int(len(x)),
                "mean": float(x.mean()),
                "sd": float(x.std(ddof=1)) if len(x) > 1 else None,
                "median": float(x.median()),
                "q1": float(x.quantile(0.25)),
                "q3": float(x.quantile(0.75)),
            }
        )
    chart = build_chart(tmp, "box", {"x": g, "y": y, "title": f"{y} by {g}"})
    return {"table": rows, "chart": chart}


def filter_df(df: pd.DataFrame, filters: list[dict]) -> pd.DataFrame:
    out = df
    for f in filters or []:
        col, op, val = f.get("column"), f.get("op"), f.get("value")
        if col not in out.columns:
            continue
        s = out[col]
        if op == "eq":
            out = out[s.astype(str) == str(val)]
        elif op == "neq":
            out = out[s.astype(str) != str(val)]
        elif op == "gt":
            out = out[pd.to_numeric(s, errors="coerce") > float(val)]
        elif op == "lt":
            out = out[pd.to_numeric(s, errors="coerce") < float(val)]
        elif op == "contains":
            out = out[s.astype(str).str.contains(str(val), case=False, na=False)]
        elif op == "in":
            vals = val if isinstance(val, list) else str(val).split(",")
            out = out[s.astype(str).isin([str(v).strip() for v in vals])]
    return out
