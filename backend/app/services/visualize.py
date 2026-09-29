from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

from .types import classify_series, column_roles


def fig_json(fig) -> dict:
    import json

    fig.update_layout(
        template="plotly_white",
        font=dict(family="IBM Plex Sans, Segoe UI, sans-serif", size=13, color="#1b2a32"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#fbfaf7",
        margin=dict(l=56, r=28, t=56, b=48),
        colorway=["#0F4C5C", "#E36414", "#2D6A4F", "#7B2D8E", "#C1121F", "#3D5A80"],
    )
    return json.loads(fig.to_json())


def recommend_chart(df: pd.DataFrame, intent: str | None, x=None, y=None) -> str:
    roles = column_roles(df)
    if y and x:
        ry, rx = roles.get(y), roles.get(x)
        if ry == "numeric" and rx == "numeric":
            return "scatter"
        if ry == "numeric" and rx in ("categorical", "boolean"):
            return "box"
        if rx == "datetime" and ry == "numeric":
            return "line"
        if ry in ("categorical", "boolean") and rx in ("categorical", "boolean"):
            return "grouped_bar"
    if y and roles.get(y) == "numeric":
        return "histogram"
    return "histogram"


def build_chart(df: pd.DataFrame, kind: str, params: dict) -> dict:
    kind = (kind or "histogram").lower()
    x, y, g = params.get("x"), params.get("y"), params.get("group") or params.get("color")
    title = params.get("title")
    if kind in ("histogram", "hist"):
        col = y or x or params.get("column")
        fig = px.histogram(df, x=col, color=g, nbins=int(params.get("bins", 30)), marginal="box", title=title or f"Distribution of {col}")
    elif kind == "box":
        fig = px.box(df, x=x, y=y, color=g or x, points="outliers", title=title or f"{y} by {x}")
    elif kind == "violin":
        fig = px.violin(df, x=x, y=y, color=g or x, box=True, points="outliers", title=title or f"{y} by {x}")
    elif kind == "scatter":
        fig = px.scatter(df, x=x, y=y, color=g, trendline=params.get("trendline", "ols"), title=title or f"{y} vs {x}")
    elif kind in ("bar", "grouped_bar"):
        if y:
            fig = px.bar(df, x=x, y=y, color=g, barmode="group", title=title)
        else:
            vc = df[x].astype(str).value_counts().reset_index()
            vc.columns = [x, "count"]
            fig = px.bar(vc, x=x, y="count", title=title or f"Counts of {x}")
    elif kind == "line":
        fig = px.line(df.sort_values(x) if x in df.columns else df, x=x, y=y, color=g, title=title or f"{y} over {x}")
    elif kind in ("heatmap", "correlation"):
        cols = params.get("columns") or [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        corr = df[cols].apply(pd.to_numeric, errors="coerce").corr()
        fig = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1, title=title or "Correlation heatmap", aspect="auto")
    elif kind == "qq":
        col = y or x or params.get("column")
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        osm, osr = stats.probplot(s, dist="norm")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=osm[0], y=osm[1], mode="markers", name="Sample"))
        fig.add_trace(go.Scatter(x=osm[0], y=osr[0] * np.array(osm[0]) + osr[1], mode="lines", name="Normal reference"))
        fig.update_layout(title=title or f"Normal Q–Q plot of {col}", xaxis_title="Theoretical quantile", yaxis_title="Sample quantile")
    elif kind == "residuals":
        # expects y and fitted in params
        fig = px.scatter(df, x=params.get("fitted") or x, y=params.get("resid") or y, title=title or "Residuals vs fitted", trendline="lowess")
    elif kind == "km":
        fig = px.line(df, x=params.get("time", "time"), y=params.get("survival", "survival"), color=params.get("group", "group"), title=title or "Kaplan–Meier")
        fig.update_yaxes(range=[0, 1], title="Ŝ(t)")
    elif kind == "pca_scatter":
        fig = px.scatter(df, x="PC1", y="PC2", color=g, title=title or "PCA scores")
    else:
        col = y or x or df.columns[0]
        fig = px.histogram(df, x=col, title=title or str(col))
    return {"kind": kind, "plotly": fig_json(fig)}


def auto_eda_charts(df: pd.DataFrame, max_charts: int = 8) -> list[dict]:
    roles = column_roles(df)
    nums = [c for c, r in roles.items() if r == "numeric"][:6]
    cats = [c for c, r in roles.items() if r in ("categorical", "boolean")][:4]
    dts = [c for c, r in roles.items() if r == "datetime"]
    charts = []
    for c in nums[:3]:
        charts.append(build_chart(df, "histogram", {"column": c, "y": c, "title": f"Distribution · {c}"}))
        charts.append(build_chart(df, "qq", {"column": c, "y": c}))
        if len(charts) >= max_charts:
            return charts
    if cats and nums:
        charts.append(build_chart(df, "box", {"x": cats[0], "y": nums[0], "title": f"{nums[0]} by {cats[0]}"}))
    if len(nums) >= 2:
        charts.append(build_chart(df, "scatter", {"x": nums[0], "y": nums[1], "title": f"{nums[1]} vs {nums[0]}"}))
        charts.append(build_chart(df, "heatmap", {"title": "Correlation heatmap"}))
    if dts and nums:
        charts.append(build_chart(df, "line", {"x": dts[0], "y": nums[0], "group": cats[0] if cats else None}))
    return charts[:max_charts]
