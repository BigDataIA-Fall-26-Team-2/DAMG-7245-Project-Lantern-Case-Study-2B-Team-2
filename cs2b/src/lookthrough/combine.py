"""Combine the monthly SEC ZIPs of one quarter (e.g. 2026q2) into one dataset.

Every row keeps a `release` column (which month it came from), and `soi_row`
stays the row number inside that month's soi.tsv, so provenance is preserved.
"""
from pathlib import Path

import pandas as pd

from .load import load_sub, load_tag, load_soi, load_num, soi_header
from .mapping import map_soi_columns, soi_usecols, to_canonical
from .paths import release_dirs  # retain the existing combine.release_dirs API

# Filers that list the portfolios of their unconsolidated JVs tag each JV row
# with this axis. Kept as `subsidiary` so two JVs holding the same loan stay
# two holdings instead of being merged as a "conflict".
SUBSIDIARY_AXIS = "Investment Company, Nonconsolidated Subsidiary Axis"


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
    if not parts:
        raise ValueError("No SOI rows available in the selected releases")
    return pd.concat(parts, ignore_index=True)


def load_inputs(rdir, *, num_tags=None, custom_fv=False,
                source_manifest=None, source_documents=None) -> dict:
    """Load consistently selected SUB, TAG, SOI and NUM inputs without cleaning.

    Accept one directory (the starter API) or an ordered release/path mapping.
    For mappings, the last listed copy of a filing wins across all tables;
    `soi` contains canonical rows and `colmap` is indexed by release. Directory
    callers retain raw `soi` and a single column map. `canon` always contains
    canonical rows, before current/comparative period classification.
    """
    # A path preserves the starter notebook API; a release/path mapping uses
    # the combined loader and retains monthly provenance for the baseline.
    if isinstance(rdir, dict):
        if not rdir:
            raise ValueError("At least one release must be selected")
        for release, directory in rdir.items():
            for relative in ("datasets/sub.tsv", "datasets/tag.tsv", "datasets/num.tsv"):
                if not (Path(directory) / relative).is_file():
                    raise FileNotFoundError(f"{release}: missing {relative}; restore data with dvc pull")
            if not has_soi(directory) and not load_sub(directory).empty:
                raise FileNotFoundError(f"{release}: missing or empty soi.tsv with non-empty SUB")
        sub = load_sub_all(rdir)
        tag = load_tag_all(rdir)
        canon = load_soi_all(rdir, tag)
        # Apply the same release winner to SUB, SOI and NUM. Otherwise repeated
        # filings can be double-counted or reconciled against a different copy.
        winner = sub.set_index("adsh")["release"]
        canon = canon[canon["release"].eq(canon["adsh"].map(winner))].copy()
        parts = []
        for release, directory in rdir.items():
            ids = set(sub.loc[sub["release"].eq(release), "adsh"])
            if ids:
                n = load_num(directory, tags=num_tags, adsh=ids, custom_fv=custom_fv)
                n["release"] = release
                parts.append(n)
        if not parts:
            raise ValueError("No current filings in the selected releases")
        num = pd.concat(parts, ignore_index=True)
        soi = canon.copy()
        colmap = {release: map_soi_columns(soi_header(d), tag)
                  for release, d in rdir.items() if has_soi(d)}
    else:
        sub, tag = load_sub(rdir), load_tag(rdir)
        header = soi_header(rdir)
        colmap = map_soi_columns(header, tag)
        soi = load_soi(rdir, soi_usecols(header, colmap))
        soi = soi[soi["adsh"].isin(sub["adsh"])]
        num = load_num(rdir, tags=num_tags, custom_fv=custom_fv)
        canon = to_canonical(soi, colmap)
    if source_manifest is not None:
        from . import evidence
        canon = evidence.attach(canon, source_manifest, source_documents)
    return {"sub": sub, "tag": tag, "colmap": colmap, "soi": soi,
            "num": num, "canon": canon}
