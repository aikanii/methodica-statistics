from __future__ import annotations

from .assumptions import check_assumptions
from .eda import explore
from .profile import profile_dataset
from .quality import assess_quality
from .recommend import recommend
from .stats_engine import run_method
from .validate import validate_result
from .visualize import auto_eda_charts, build_chart, recommend_chart
from .cleaning import propose_from_quality


def run_autopilot(df, question: str, apply_cleaning: bool = False) -> dict:
    steps = []

    def step(key, title, status, payload=None, note=None):
        rec = {"key": key, "title": title, "status": status, "note": note, "payload": payload}
        steps.append(rec)
        return rec

    step("profile", "Profile dataset", "done", profile_dataset(df))
    qlt = assess_quality(df)
    step("quality", "Data-quality assessment", "done", qlt)
    proposals = propose_from_quality(qlt["issues"])
    step(
        "cleaning_proposal",
        "Proposed cleaning",
        "awaiting_approval" if proposals and not apply_cleaning else "done",
        {"proposals": proposals, "message": "The system proposes these changes."},
        note="Cleaning is never applied silently.",
    )

    eda = explore(df)
    step("eda", "Exploratory analysis", "done", {"descriptives": eda["descriptives"][:12], "n_charts": len(eda["charts"])})

    rec = recommend(df, question)
    step("recommend", "Method selection", "done", rec)

    checks = check_assumptions(df, rec["recommended"], rec["params"])
    step("assumptions", "Assumption checks", "done", checks)

    analysis = None
    validation = None
    try:
        analysis = run_method(df, rec["recommended"], rec["params"])
        step("analysis", "Statistical analysis", "done", analysis)
        validation = validate_result(rec["recommended"], rec["params"], analysis, checks)
        step("validate", "Result validation", "done", validation)
    except Exception as e:
        step("analysis", "Statistical analysis", "error", {"error": str(e)})
        analysis = {
            "method": rec["recommended"],
            "method_label": rec.get("recommended_label"),
            "summary": f"Analysis could not be completed. {e}",
            "interpretation": str(e),
            "statistics": {},
            "warnings": [str(e)],
            "tables": {},
        }

    charts = []
    try:
        y, x = rec.get("dependent"), rec.get("independent")
        kind = recommend_chart(df, rec.get("intent"), x, y)
        charts.append(build_chart(df, kind, {"x": x, "y": y, "title": f"{kind}: {y} vs {x}"}))
        charts.extend(auto_eda_charts(df, max_charts=3))
        step("viz", "Visualizations", "done", {"n": len(charts)})
    except Exception as e:
        step("viz", "Visualizations", "error", {"error": str(e)})

    interpretation = (analysis or {}).get("interpretation") or ""
    step("interpret", "Interpretation", "done", {"text": interpretation})
    step("report", "Report", "ready", {"style_options": ["academic", "business", "scientific", "general"]})

    return {
        "question": question,
        "steps": steps,
        "recommendation": rec,
        "assumptions": checks,
        "analysis": analysis,
        "validation": validation,
        "charts": charts,
        "interpretation": interpretation,
        "quality": qlt,
        "profile": steps[0]["payload"],
        "cleaning_proposals": proposals,
    }
