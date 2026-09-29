from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd


SUPPORTED = {".csv", ".xlsx", ".xls", ".json", ".parquet", ".pq", ".tsv", ".txt", ".sqlite", ".db"}


def load_bytes(filename: str, data: bytes) -> pd.DataFrame:
    name = filename.lower()
    buf = io.BytesIO(data)
    if name.endswith(".csv") or name.endswith(".txt"):
        return _read_csv(buf)
    if name.endswith(".tsv"):
        return pd.read_csv(buf, sep="\t")
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(buf)
    if name.endswith(".json"):
        text = data.decode("utf-8", errors="replace")
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            buf.seek(0)
            return pd.read_json(buf, lines=True)
        if isinstance(obj, list):
            return pd.DataFrame(obj)
        if isinstance(obj, dict):
            if "data" in obj and isinstance(obj["data"], list):
                return pd.DataFrame(obj["data"])
            return pd.json_normalize(obj)
        raise ValueError("Unsupported JSON structure")
    if name.endswith(".parquet") or name.endswith(".pq"):
        return pd.read_parquet(buf)
    if name.endswith(".sqlite") or name.endswith(".db"):
        import sqlite3
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        conn = sqlite3.connect(tmp_path)
        tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
        if tables.empty:
            conn.close()
            raise ValueError("SQLite file contains no tables")
        tname = tables.iloc[0, 0]
        df = pd.read_sql(f'SELECT * FROM "{tname}"', conn)
        conn.close()
        return df
    # fallback
    return _read_csv(buf)


def _read_csv(buf: io.BytesIO) -> pd.DataFrame:
    buf.seek(0)
    try:
        return pd.read_csv(buf)
    except Exception:
        buf.seek(0)
        return pd.read_csv(buf, encoding="latin-1")


def load_sql(connection_url: str, query: str | None = None, table: str | None = None) -> pd.DataFrame:
    from sqlalchemy import create_engine

    engine = create_engine(connection_url)
    if query:
        return pd.read_sql(query, engine)
    if table:
        return pd.read_sql_table(table, engine)
    raise ValueError("Provide a SQL query or table name")


def merge_frames(frames: list[pd.DataFrame], how: str = "concat") -> pd.DataFrame:
    if not frames:
        raise ValueError("No datasets to merge")
    if len(frames) == 1:
        return frames[0]
    if how == "concat":
        return pd.concat(frames, ignore_index=True, sort=False)
    return frames[0]


def infer_datetime(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object:
            sample = out[col].dropna().astype(str).head(30)
            if sample.empty:
                continue
            if sample.str.match(r"^\d{4}-\d{2}-\d{2}").mean() > 0.7:
                parsed = pd.to_datetime(out[col], errors="coerce")
                if parsed.notna().mean() > 0.7:
                    out[col] = parsed
    return out
