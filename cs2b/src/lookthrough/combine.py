"""Combine the monthly SEC ZIPs of one quarter (e.g. 2026q2) into one dataset.

Every row keeps a `release` column (which month it came from), and `soi_row`
stays the row number inside that month's soi.tsv, so provenance is preserved.
"""
from pathlib import Path

import pandas as pd

from .load import load_sub, load_tag, load_soi, soi_header
from .mapping import map_soi_columns, soi_usecols, to_canonical
from .paths import repo_root

# Filers that list the portfolios of their unconsolidated JVs tag each JV row
# with this axis. Kept as `subsidiary` so two JVs holding the same loan stay
# two holdings instead of being merged as a "conflict".
SUBSIDIARY_AXIS = "Investment Company, Nonconsolidated Subsidiary Axis"


def release_dirs(params: dict, root=None) -> dict:
    """{month: folder} for every month in params['releases'] (or the single release)."""
    root = Path(root) if root else repo_root()
    months = params.get("releases") or [params["release"]]
    raw = root / params["data"]["raw_dir"]
    return {m: raw / f"{m}_bdc" for m in months}


def has_soi(d) -> bool:
    """False for a month whose soi.tsv is missing or empty (e.g. 2026_06)."""
    p = Path(d) / "soi.tsv"
    return p.exists() and p.stat().st_size > 0


def load_sub_all(dirs: dict) -> pd.DataFrame:
    """Filings from every month; if a filing appears twice, keep the later month."""
    parts = []
    for m, d in dirs.items():
        s = load_sub(d)
        s.insert(0, "release", m)
        parts.append(s)
    sub = pd.concat(parts, ignore_index=True)
    return sub.drop_duplicates("adsh", keep="last").reset_index(drop=True)


def load_tag_all(dirs: dict) -> pd.DataFrame:
    """TAG tables of every month merged, so a label known in any month
    (e.g. the us-gaap/2026 'Initial fair value of Investment') maps in all."""
    tag = pd.concat([load_tag(d) for d in dirs.values()], ignore_index=True)
    return tag.drop_duplicates(["tag", "version"]).reset_index(drop=True)


def load_soi_all(dirs: dict, tag=None) -> pd.DataFrame:
    """Canonical SOI rows of every month, with `release`, per-month `soi_row`
    and `subsidiary` (the JV a row belongs to, if the filer tags one)."""
    tag = load_tag_all(dirs) if tag is None else tag
    parts = []
    for m, d in dirs.items():
        if not has_soi(d):
            continue
        header = soi_header(d)
        colmap = map_soi_columns(header, tag)
        cols = soi_usecols(header, colmap)
        if SUBSIDIARY_AXIS in header:
            cols.append(SUBSIDIARY_AXIS)
        soi = load_soi(d, usecols=cols)
        can = to_canonical(soi, colmap)
        can["subsidiary"] = (soi[SUBSIDIARY_AXIS]
                             if SUBSIDIARY_AXIS in soi.columns else pd.NA)
        can.insert(0, "release", m)
        parts.append(can)
    return pd.concat(parts, ignore_index=True)