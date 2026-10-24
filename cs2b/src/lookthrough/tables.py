"""Save and load tables as Parquet when pyarrow is installed, else as gzipped CSV."""
from pathlib import Path

import pandas as pd


def _has_parquet() -> bool:
    try:
        import pyarrow  # noqa: F401
        return True
    except ImportError:
        return False


def save_table(df: pd.DataFrame, stem) -> Path:
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    if _has_parquet():
        p = stem.with_suffix(".parquet"); df.to_parquet(p, index=False)
    else:
        p = stem.with_suffix(".csv.gz"); df.to_csv(p, index=False)
    return p


def load_table(stem) -> pd.DataFrame:
    stem = Path(stem)
    for suffix, reader in ((".parquet", pd.read_parquet), (".csv.gz", pd.read_csv), (".csv", pd.read_csv)):
        p = stem.with_suffix(suffix)
        if p.exists():
            return reader(p, dtype={"adsh": str, "cik": str, "source_rows": str}) \
                if reader is not pd.read_parquet else reader(p)
    raise FileNotFoundError(f"no table at {stem}.parquet or {stem}.csv.gz")
