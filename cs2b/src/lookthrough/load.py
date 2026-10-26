"""Read the release tables with explicit types; normalize dates."""
from pathlib import Path

import pandas as pd

READ = dict(sep="\t", dtype=str, keep_default_na=False,
            na_values=[""], low_memory=False)


def norm_date(s: pd.Series) -> pd.Series:
    """YYYYMMDD, MM/DD/YYYY or YYYY-MM-DD -> 'YYYY-MM-DD'."""
    s = s.astype("string").str.strip()
    out = pd.Series(pd.NA, index=s.index, dtype="string")
    ymd = s.str.fullmatch(r"\d{8}").fillna(False)
    v = s[ymd]
    out[ymd] = v.str[:4] + "-" + v.str[4:6] + "-" + v.str[6:8]
    iso = s.str.fullmatch(r"\d{4}-\d{2}-\d{2}").fillna(False)
    out[iso] = s[iso]
    us = s.str.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}").fillna(False)
    if us.any():
        p = s[us].str.split("/", expand=True)
        out[us] = (p[2] + "-" + p[0].str.zfill(2) + "-"
                   + p[1].str.zfill(2))
    return out


def load_sub(rdir) -> pd.DataFrame:
    """Filings, keeping the latest version (prevrpt != '1')."""
    sub = pd.read_csv(Path(rdir) / "datasets" / "sub.tsv", **READ)
    sub["period"] = norm_date(sub["period"])
    return sub[sub["prevrpt"] != "1"].reset_index(drop=True)


def load_tag(rdir) -> pd.DataFrame:
    return pd.read_csv(Path(rdir) / "datasets" / "tag.tsv", **READ)


def load_num(rdir, tags=None, adsh=None, custom_fv=False,
             chunksize=500_000) -> pd.DataFrame:
    """NUM is large: read in chunks, keep only what you need.
    custom_fv also keeps custom-tag facts named like fair value."""
    path = Path(rdir) / "datasets" / "num.tsv"
    keep = []
    for ch in pd.read_csv(path, chunksize=chunksize, **READ):
        m = pd.Series(tags is None, index=ch.index)
        if tags is not None:
            m = ch["tag"].isin(tags)
        if custom_fv:
            m = m | ((ch["version"] == ch["adsh"]) & ch["tag"]
                     .str.contains("FairValue", case=False, na=False))
        if adsh is not None:
            m = m & ch["adsh"].isin(adsh)
        keep.append(ch[m])
    num = pd.concat(keep, ignore_index=True)
    num["ddate"] = norm_date(num["ddate"])
    num["value"] = pd.to_numeric(num["value"], errors="coerce")
    return num


def soi_header(rdir) -> list:
    """SOI column names, without loading the file."""
    with open(Path(rdir) / "soi.tsv", encoding="utf-8") as fh:
        return fh.readline().rstrip("\n").split("\t")


def load_soi(rdir, usecols=None) -> pd.DataFrame:
    """The SOI report; soi_row = 0-based data row (provenance).
    usecols limits the columns read (memory), never the rows."""
    want = None if usecols is None else set(usecols)
    pick = (lambda c: c in want) if want else None
    soi = pd.read_csv(Path(rdir) / "soi.tsv", usecols=pick, **READ)
    soi.insert(0, "soi_row", range(len(soi)))
    for c in ("ddate", "period", "filed"):
        if c in soi.columns:
            soi[c] = norm_date(soi[c])
    return soi
