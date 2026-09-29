from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import models
from .auth import create_token, get_current_user, hash_password, verify_password
from .config import APP_NAME, APP_VERSION, EXPORTS, MAX_PREVIEW_ROWS, MAX_UPLOAD_MB, SAMPLE_DATA, UPLOADS
from .db import Base, SessionLocal, engine, get_db
from .errors import error_payload
from .models import Analysis, AuditLog, Conversation, Dataset, DatasetVersion, Message, Project, Report, Transformation, User
from .services import autopilot as autopilot_svc
from .services import assistant as assistant_svc
from .services.assumptions import check_assumptions
from .services.cleaning import apply_operation, propose_from_quality
from .services.eda import explore, filter_df, group_compare
from .services.io_load import infer_datetime, load_bytes, load_sql, merge_frames
from .services.profile import profile_dataset
from .services.quality import assess_quality
from .services.recommend import recommend as recommend_method
from .services.reports import build_report_payload, export_report, to_markdown
from .services.stats_engine import METHOD_META, run_method
from .services.store import commit_new_version, load_df, save_original, write_version
from .services.validate import validate_result
from .services.visualize import build_chart, recommend_chart
from .utils import df_records, new_id, to_native

Base.metadata.create_all(bind=engine)

app = FastAPI(title=APP_NAME, version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def audit(db: Session, user_id: str | None, action: str, detail: str = ""):
    db.add(AuditLog(id=new_id(), user_id=user_id, action=action, detail=detail[:4000]))
    db.commit()


def seed():
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == "demo@methodica.app").first():
            u = User(
                id=new_id(),
                email="demo@methodica.app",
                name="Demo Analyst",
                password_hash=hash_password("demo1234"),
                role="analyst",
            )
            db.add(u)
            db.commit()
        _ensure_sample_files()
    finally:
        db.close()


def _ensure_sample_files():
    SAMPLE_DATA.mkdir(parents=True, exist_ok=True)
    air = SAMPLE_DATA / "air_quality.csv"
    if not air.exists():
        from .sample_gen import write_samples

        write_samples()


seed()


@app.get("/api/health")
def health():
    return {"ok": True, "app": APP_NAME, "version": APP_VERSION}


# ── Auth ─────────────────────────────────────────────────────


@app.post("/api/auth/register")
def register(body: dict, db: Session = Depends(get_db)):
    email = (body.get("email") or "").strip().lower()
    name = body.get("name") or email.split("@")[0]
    password = body.get("password") or ""
    if not email or len(password) < 6:
        raise HTTPException(400, "Email and a password of at least 6 characters are required.")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "An account with that email already exists.")
    u = User(id=new_id(), email=email, name=name, password_hash=hash_password(password), role="analyst")
    db.add(u)
    db.commit()
    token = create_token(u.id, u.email)
    return {"token": token, "user": {"id": u.id, "email": u.email, "name": u.name, "role": u.role}}


@app.post("/api/auth/login")
def login(body: dict, db: Session = Depends(get_db)):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    u = db.query(User).filter(User.email == email).first()
    if not u or not verify_password(password, u.password_hash):
        raise HTTPException(401, "Invalid email or password.")
    token = create_token(u.id, u.email)
    audit(db, u.id, "login")
    return {"token": token, "user": {"id": u.id, "email": u.email, "name": u.name, "role": u.role}}


@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role}


# ── Projects ─────────────────────────────────────────────────


@app.get("/api/projects")
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Project).filter(Project.user_id == user.id).order_by(Project.updated_at.desc()).all()
    out = []
    for p in rows:
        n_ds = db.query(Dataset).filter(Dataset.project_id == p.id).count()
        n_an = db.query(Analysis).filter(Analysis.project_id == p.id).count()
        out.append(
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "n_datasets": n_ds,
                "n_analyses": n_an,
            }
        )
    return out


@app.post("/api/projects")
def create_project(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = Project(id=new_id(), user_id=user.id, name=body.get("name") or "Untitled project", description=body.get("description") or "")
    db.add(p)
    db.commit()
    return {"id": p.id, "name": p.name, "description": p.description}


@app.delete("/api/projects/{pid}")
def delete_project(pid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == pid, Project.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Project not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


# ── Datasets ─────────────────────────────────────────────────


def _own_dataset(db, user, did) -> Dataset:
    ds = db.query(Dataset).filter(Dataset.id == did, Dataset.user_id == user.id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    return ds


@app.get("/api/datasets")
def list_datasets(project_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Dataset).filter(Dataset.user_id == user.id)
    if project_id:
        q = q.filter(Dataset.project_id == project_id)
    rows = q.order_by(Dataset.created_at.desc()).all()
    return [
        {
            "id": d.id,
            "project_id": d.project_id,
            "name": d.name,
            "n_rows": d.n_rows,
            "n_cols": d.n_cols,
            "version": d.current_version,
            "quality_score": d.quality_score,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "original_filename": d.original_filename,
        }
        for d in rows
    ]


def _ingest_frame(db, user, project_id, name, filename, df: pd.DataFrame, source_type="file") -> Dataset:
    df = infer_datetime(df)
    if project_id:
        proj = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
        if not proj:
            raise HTTPException(400, "Project not found")
    else:
        proj = db.query(Project).filter(Project.user_id == user.id).order_by(Project.created_at.desc()).first()
        if not proj:
            proj = Project(id=new_id(), user_id=user.id, name="Default project", description="")
            db.add(proj)
            db.commit()
    ds = Dataset(
        id=new_id(),
        project_id=proj.id,
        user_id=user.id,
        name=name or filename or "Untitled dataset",
        original_filename=filename,
        source_type=source_type,
        n_rows=int(len(df)),
        n_cols=int(df.shape[1]),
        current_version=1,
    )
    path = write_version(df, ds.id, 1)
    db.add(ds)
    db.add(DatasetVersion(id=new_id(), dataset_id=ds.id, version=1, path=str(path), note="Original ingest"))
    db.commit()
    try:
        prof = profile_dataset(df)
        ds.quality_score = prof["quality_score"]
        db.add(ds)
        db.commit()
    except Exception:
        pass
    return ds


@app.post("/api/datasets/upload")
async def upload_dataset(
    files: list[UploadFile] = File(...),
    project_id: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    frames = []
    names = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(400, f"{f.filename} exceeds the {MAX_UPLOAD_MB} MB upload limit.")
        try:
            df = load_bytes(f.filename or "data.csv", data)
        except Exception as e:
            raise HTTPException(400, f"Could not parse {f.filename}: {e}")
        frames.append(df)
        names.append(f.filename)
    df = merge_frames(frames, "concat") if len(frames) > 1 else frames[0]
    name = names[0] if len(names) == 1 else f"merged_{len(names)}_files"
    ds = _ingest_frame(db, user, project_id, name, names[0], df)
    for f, raw in zip(files, []):
        pass
    # save first original
    try:
        # re-read not available; skip
        pass
    except Exception:
        pass
    audit(db, user.id, "upload", ds.id)
    return {"id": ds.id, "name": ds.name, "n_rows": ds.n_rows, "n_cols": ds.n_cols, "project_id": ds.project_id}


@app.post("/api/datasets/from-sql")
def from_sql(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        df = load_sql(body.get("url"), body.get("query"), body.get("table"))
    except Exception as e:
        raise HTTPException(400, f"SQL import failed: {e}")
    ds = _ingest_frame(db, user, body.get("project_id"), body.get("name") or "SQL extract", "sql", df, source_type="sql")
    return {"id": ds.id, "name": ds.name, "n_rows": ds.n_rows, "n_cols": ds.n_cols}


@app.post("/api/datasets/sample/{which}")
def load_sample(which: str, project_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_sample_files()
    mapping = {
        "air": SAMPLE_DATA / "air_quality.csv",
        "clinical": SAMPLE_DATA / "clinical_trial.csv",
        "survey": SAMPLE_DATA / "survey_items.csv",
    }
    path = mapping.get(which)
    if not path or not path.exists():
        raise HTTPException(404, "Unknown sample")
    df = pd.read_csv(path)
    ds = _ingest_frame(db, user, project_id, path.name, path.name, df, source_type="sample")
    return {"id": ds.id, "name": ds.name, "n_rows": ds.n_rows, "n_cols": ds.n_cols, "project_id": ds.project_id}


@app.get("/api/datasets/{did}")
def get_dataset(did: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    return {
        "id": ds.id,
        "project_id": ds.project_id,
        "name": ds.name,
        "n_rows": ds.n_rows,
        "n_cols": ds.n_cols,
        "version": ds.current_version,
        "quality_score": ds.quality_score,
        "original_filename": ds.original_filename,
        "source_type": ds.source_type,
    }


@app.delete("/api/datasets/{did}")
def delete_dataset(did: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    import shutil

    ds = _own_dataset(db, user, did)
    db.query(DatasetVersion).filter(DatasetVersion.dataset_id == ds.id).delete()
    db.query(Transformation).filter(Transformation.dataset_id == ds.id).delete()
    db.query(Analysis).filter(Analysis.dataset_id == ds.id).delete()
    db.query(Report).filter(Report.dataset_id == ds.id).delete()
    convs = db.query(Conversation).filter(Conversation.dataset_id == ds.id).all()
    conv_ids = [c.id for c in convs]
    if conv_ids:
        db.query(Message).filter(Message.conversation_id.in_(conv_ids)).delete(synchronize_session=False)
    db.query(Conversation).filter(Conversation.dataset_id == ds.id).delete()
    db.delete(ds)
    db.commit()
    shutil.rmtree(UPLOADS / ds.id, ignore_errors=True)
    audit(db, user.id, "delete_dataset", did)
    return {"ok": True, "id": did}


@app.get("/api/datasets/{did}/preview")
def preview(did: str, offset: int = 0, limit: int = 80, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    df = load_df(ds)
    limit = min(limit, MAX_PREVIEW_ROWS)
    sl = df.iloc[offset : offset + limit]
    return {
        "columns": [str(c) for c in df.columns],
        "rows": df_records(sl),
        "offset": offset,
        "limit": limit,
        "n_rows": int(len(df)),
        "n_cols": int(df.shape[1]),
        "dtypes": {str(c): str(df[c].dtype) for c in df.columns},
    }


@app.get("/api/datasets/{did}/profile")
def profile(did: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    df = load_df(ds)
    prof = profile_dataset(df)
    ds.quality_score = prof["quality_score"]
    db.add(ds)
    db.commit()
    return prof


@app.get("/api/datasets/{did}/quality")
def quality(did: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    df = load_df(ds)
    q = assess_quality(df)
    q["proposals"] = propose_from_quality(q["issues"])
    q["message"] = "The system proposes these changes."
    return q


@app.get("/api/datasets/{did}/history")
def history(did: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    vers = db.query(DatasetVersion).filter(DatasetVersion.dataset_id == ds.id).order_by(DatasetVersion.version).all()
    ops = db.query(Transformation).filter(Transformation.dataset_id == ds.id).order_by(Transformation.created_at).all()
    return {
        "current": ds.current_version,
        "versions": [{"version": v.version, "note": v.note, "created_at": v.created_at.isoformat() if v.created_at else None} for v in vers],
        "transformations": [
            {
                "id": t.id,
                "operation": t.operation,
                "params": json.loads(t.params_json or "{}"),
                "version_from": t.version_from,
                "version_to": t.version_to,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in ops
        ],
    }


@app.post("/api/datasets/{did}/clean")
def clean(did: str, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    df = load_df(ds)
    ops = body.get("operations") or ([body] if body.get("operation") else [])
    notes = []
    for op in ops:
        try:
            df, note = apply_operation(df, op)
            notes.append(note)
        except Exception as e:
            raise HTTPException(400, error_payload("Cleaning could not be completed.", e)["message"] + f" ({e})")
    rec = commit_new_version(db, ds, df, "; ".join(notes))
    for op, note in zip(ops, notes):
        db.add(
            Transformation(
                id=new_id(),
                dataset_id=ds.id,
                version_from=rec.version - 1,
                version_to=rec.version,
                operation=op.get("operation"),
                params_json=json.dumps(op, default=str),
            )
        )
    db.commit()
    return {"version": ds.current_version, "n_rows": ds.n_rows, "n_cols": ds.n_cols, "notes": notes}


@app.post("/api/datasets/{did}/undo")
def undo(did: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    if ds.current_version <= 1:
        raise HTTPException(400, "Nothing to undo.")
    ds.current_version = ds.current_version - 1
    df = load_df(ds)
    ds.n_rows, ds.n_cols = int(len(df)), int(df.shape[1])
    db.add(ds)
    db.commit()
    return {"version": ds.current_version, "n_rows": ds.n_rows, "n_cols": ds.n_cols}


@app.post("/api/datasets/{did}/restore")
def restore(did: str, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    v = int(body.get("version", 1))
    ds.current_version = v
    df = load_df(ds)
    ds.n_rows, ds.n_cols = int(len(df)), int(df.shape[1])
    db.add(ds)
    db.commit()
    return {"version": v, "n_rows": ds.n_rows}


# ── Explore ──────────────────────────────────────────────────


@app.post("/api/datasets/{did}/explore")
def explore_ep(did: str, body: dict | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    df = load_df(ds)
    body = body or {}
    if body.get("filters"):
        df = filter_df(df, body["filters"])
    return explore(df, body)


@app.post("/api/datasets/{did}/group")
def group_ep(did: str, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    df = load_df(ds)
    return group_compare(df, body.get("y"), body.get("group") or body.get("x"))


@app.post("/api/datasets/{did}/chart")
def chart_ep(did: str, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    df = load_df(ds)
    kind = body.get("kind") or recommend_chart(df, None, body.get("x"), body.get("y"))
    return build_chart(df, kind, body)


# ── Analyze ──────────────────────────────────────────────────


@app.get("/api/methods")
def methods():
    return METHOD_META


@app.post("/api/datasets/{did}/recommend")
def recommend_ep(did: str, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    df = load_df(ds)
    rec = recommend_method(df, body.get("question") or "", body.get("hint"))
    rec["assumptions_preview"] = check_assumptions(df, rec["recommended"], rec["params"])
    return rec


@app.post("/api/datasets/{did}/assumptions")
def assumptions_ep(did: str, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    df = load_df(ds)
    return {"checks": check_assumptions(df, body.get("method"), body.get("params") or {})}


@app.post("/api/datasets/{did}/analyze")
def analyze_ep(did: str, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    df = load_df(ds)
    method = body.get("method")
    params = body.get("params") or {}
    question = body.get("question") or ""
    try:
        checks = check_assumptions(df, method, params)
        result = run_method(df, method, params)
        validation = validate_result(method, params, result, checks)
    except Exception as e:
        payload = error_payload("Analysis could not be completed.", e)
        payload["trace"] = traceback.format_exc()[-2500:]
        return JSONResponse(status_code=400, content=payload)
    prov = {
        "dataset_id": ds.id,
        "dataset_version": ds.current_version,
        "method": method,
        "params": params,
        "question": question,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "software": f"{APP_NAME} {APP_VERSION}",
        "n_rows": ds.n_rows,
        "n_cols": ds.n_cols,
        "assumptions": checks,
    }
    rec = Analysis(
        id=new_id(),
        dataset_id=ds.id,
        user_id=user.id,
        project_id=ds.project_id,
        research_question=question,
        method=method,
        params_json=json.dumps(params, default=str),
        result_json=json.dumps(result, default=str),
        provenance_json=json.dumps(prov, default=str),
    )
    db.add(rec)
    db.commit()
    # optional chart
    chart = None
    try:
        kind = recommend_chart(df, None, params.get("x") if isinstance(params.get("x"), str) else None, params.get("y"))
        chart = build_chart(
            df,
            kind,
            {
                "x": params.get("x") if isinstance(params.get("x"), str) else (params.get("x")[0] if isinstance(params.get("x"), list) and params.get("x") else None),
                "y": params.get("y") or params.get("column"),
                "group": params.get("group"),
            },
        )
    except Exception:
        chart = None
    return to_native(
        {
            "analysis_id": rec.id,
            "result": result,
            "assumptions": checks,
            "validation": validation,
            "provenance": prov,
            "chart": chart,
        }
    )


@app.get("/api/analyses")
def list_analyses(dataset_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Analysis).filter(Analysis.user_id == user.id)
    if dataset_id:
        q = q.filter(Analysis.dataset_id == dataset_id)
    rows = q.order_by(Analysis.created_at.desc()).limit(50).all()
    return [
        {
            "id": a.id,
            "dataset_id": a.dataset_id,
            "method": a.method,
            "question": a.research_question,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ]


@app.get("/api/analyses/{aid}")
def get_analysis(aid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.query(Analysis).filter(Analysis.id == aid, Analysis.user_id == user.id).first()
    if not a:
        raise HTTPException(404, "Analysis not found")
    return {
        "id": a.id,
        "method": a.method,
        "question": a.research_question,
        "params": json.loads(a.params_json or "{}"),
        "result": json.loads(a.result_json or "{}"),
        "provenance": json.loads(a.provenance_json or "{}"),
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@app.post("/api/analyses/{aid}/reproduce")
def reproduce(aid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.query(Analysis).filter(Analysis.id == aid, Analysis.user_id == user.id).first()
    if not a:
        raise HTTPException(404, "Analysis not found")
    ds = _own_dataset(db, user, a.dataset_id)
    # restore version if recorded
    prov = json.loads(a.provenance_json or "{}")
    v = prov.get("dataset_version")
    if v and v != ds.current_version:
        ds.current_version = v
    df = load_df(ds)
    params = json.loads(a.params_json or "{}")
    checks = check_assumptions(df, a.method, params)
    result = run_method(df, a.method, params)
    validation = validate_result(a.method, params, result, checks)
    return {"result": result, "assumptions": checks, "validation": validation, "reproduced_from": a.id, "version_used": ds.current_version}


# ── Autopilot ────────────────────────────────────────────────


@app.post("/api/datasets/{did}/autopilot")
def autopilot_ep(did: str, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    df = load_df(ds)
    try:
        out = autopilot_svc.run_autopilot(df, body.get("question") or "", bool(body.get("apply_cleaning")))
    except Exception as e:
        return JSONResponse(status_code=400, content=error_payload("Autopilot could not finish.", e))
    rec = Analysis(
        id=new_id(),
        dataset_id=ds.id,
        user_id=user.id,
        project_id=ds.project_id,
        research_question=body.get("question") or "",
        method=out.get("recommendation", {}).get("recommended"),
        params_json=json.dumps(out.get("recommendation", {}).get("params") or {}, default=str),
        result_json=json.dumps(out.get("analysis") or {}, default=str),
        provenance_json=json.dumps({"mode": "autopilot", "timestamp": datetime.utcnow().isoformat() + "Z", "version": ds.current_version}, default=str),
    )
    db.add(rec)
    db.commit()
    out["analysis_id"] = rec.id
    return to_native(out)


# ── Assistant ────────────────────────────────────────────────


@app.post("/api/datasets/{did}/assistant")
def assistant_ep(did: str, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    df = load_df(ds)
    q = body.get("question") or body.get("content") or ""
    conv_id = body.get("conversation_id")
    if not conv_id:
        conv = Conversation(id=new_id(), dataset_id=ds.id, user_id=user.id)
        db.add(conv)
        db.commit()
        conv_id = conv.id
    db.add(Message(id=new_id(), conversation_id=conv_id, role="user", content=q))
    db.commit()
    ans = assistant_svc.answer(df, q)
    db.add(
        Message(
            id=new_id(),
            conversation_id=conv_id,
            role="assistant",
            content=ans.get("content") or "",
            citations_json=json.dumps(ans.get("citations") or [], default=str),
        )
    )
    db.commit()
    ans["conversation_id"] = conv_id
    return ans


# ── Reports ──────────────────────────────────────────────────


@app.post("/api/datasets/{did}/report")
def report_ep(did: str, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    df = load_df(ds)
    analysis = body.get("analysis")
    rec = body.get("recommendation")
    assumptions = body.get("assumptions") or []
    validation = body.get("validation")
    question = body.get("question") or ""
    if body.get("analysis_id") and not analysis:
        a = db.query(Analysis).filter(Analysis.id == body["analysis_id"], Analysis.user_id == user.id).first()
        if a:
            analysis = json.loads(a.result_json or "{}")
            question = question or a.research_question
    if not analysis and question:
        rec = rec or recommend_method(df, question)
        assumptions = check_assumptions(df, rec["recommended"], rec["params"])
        analysis = run_method(df, rec["recommended"], rec["params"])
        validation = validate_result(rec["recommended"], rec["params"], analysis, assumptions)
    prof = profile_dataset(df)
    qlt = assess_quality(df)
    ops = db.query(Transformation).filter(Transformation.dataset_id == ds.id).all()
    cleaning = [f"{t.operation}: {t.params_json}" for t in ops]
    payload = build_report_payload(
        dataset_name=ds.name,
        profile=prof,
        quality=qlt,
        cleaning=cleaning,
        question=question,
        recommendation=rec,
        assumptions=assumptions,
        analysis=analysis,
        validation=validation,
        interpretation=(analysis or {}).get("interpretation") or "",
        style=body.get("style") or "academic",
    )
    fmt = body.get("format") or "html"
    path = export_report(payload, fmt)
    r = Report(
        id=new_id(),
        dataset_id=ds.id,
        user_id=user.id,
        title=payload["title"][:200],
        style=payload["style"],
        path=str(path),
        format=fmt,
    )
    db.add(r)
    db.commit()
    return {
        "id": r.id,
        "title": r.title,
        "format": fmt,
        "path": str(path),
        "markdown": to_markdown(payload) if fmt in ("html", "md", "markdown") else None,
        "download": f"/api/reports/{r.id}/download",
        "payload": payload if body.get("include_payload") else None,
    }


@app.get("/api/reports")
def list_reports(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Report).filter(Report.user_id == user.id).order_by(Report.created_at.desc()).all()
    return [
        {"id": r.id, "title": r.title, "format": r.format, "style": r.style, "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]


@app.get("/api/reports/{rid}/download")
def download_report(rid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.query(Report).filter(Report.id == rid, Report.user_id == user.id).first()
    if not r or not r.path or not Path(r.path).exists():
        raise HTTPException(404, "Report file not found")
    return FileResponse(r.path, filename=Path(r.path).name)


@app.post("/api/datasets/{did}/export")
def export_data(did: str, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ds = _own_dataset(db, user, did)
    df = load_df(ds)
    fmt = body.get("format") or "csv"
    EXPORTS.mkdir(parents=True, exist_ok=True)
    path = EXPORTS / f"{ds.id}.{fmt}"
    if fmt == "csv":
        df.to_csv(path, index=False)
    elif fmt == "xlsx":
        df.to_excel(path, index=False)
    elif fmt == "parquet":
        df.to_parquet(path, index=False)
    elif fmt == "json":
        df.to_json(path, orient="records")
    else:
        raise HTTPException(400, "Unsupported export format")
    return FileResponse(path, filename=path.name)


@app.get("/api/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = db.query(Project).filter(Project.user_id == user.id).count()
    datasets = db.query(Dataset).filter(Dataset.user_id == user.id).all()
    analyses = db.query(Analysis).filter(Analysis.user_id == user.id).order_by(Analysis.created_at.desc()).limit(8).all()
    reports = db.query(Report).filter(Report.user_id == user.id).count()
    return {
        "user": {"name": user.name, "email": user.email},
        "counts": {"projects": projects, "datasets": len(datasets), "analyses": db.query(Analysis).filter(Analysis.user_id == user.id).count(), "reports": reports},
        "datasets": [
            {"id": d.id, "name": d.name, "n_rows": d.n_rows, "n_cols": d.n_cols, "quality_score": d.quality_score, "version": d.current_version}
            for d in datasets[:8]
        ],
        "analyses": [
            {"id": a.id, "method": a.method, "question": a.research_question, "created_at": a.created_at.isoformat() if a.created_at else None, "dataset_id": a.dataset_id}
            for a in analyses
        ],
    }
