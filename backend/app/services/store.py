from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import UPLOADS
from ..models import Dataset, DatasetVersion
from ..utils import new_id


def dataset_dir(dataset_id: str) -> Path:
    p = UPLOADS / dataset_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def version_path(dataset_id: str, version: int) -> Path:
    return dataset_dir(dataset_id) / f"v{version}.parquet"


def save_original(dataset_id: str, filename: str, data: bytes) -> Path:
    p = dataset_dir(dataset_id) / f"original_{filename}"
    p.write_bytes(data)
    return p


def write_version(df: pd.DataFrame, dataset_id: str, version: int) -> Path:
    path = version_path(dataset_id, version)
    df.to_parquet(path, index=False)
    return path


def load_df(dataset: Dataset) -> pd.DataFrame:
    path = version_path(dataset.id, dataset.current_version)
    if not path.exists():
        raise FileNotFoundError("Dataset version file is missing")
    return pd.read_parquet(path)


def commit_new_version(db, dataset: Dataset, df: pd.DataFrame, note: str) -> DatasetVersion:
    v = int(dataset.current_version) + 1
    path = write_version(df, dataset.id, v)
    dataset.current_version = v
    dataset.n_rows = int(len(df))
    dataset.n_cols = int(df.shape[1])
    rec = DatasetVersion(
        id=new_id(),
        dataset_id=dataset.id,
        version=v,
        path=str(path),
        note=note,
    )
    db.add(rec)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return rec
