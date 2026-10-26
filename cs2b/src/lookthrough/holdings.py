"""From canonical SOI rows to one row per holding."""
import pandas as pd

from .mapping import CANONICAL

KEY = ["adsh", "ddate", "identifier"]
TEXT = ["investment_type", "industry", "affiliation"]
META = ["cik", "name", "form", "period", "cstm", "inlineurl",
        "is_current"]


def split_periods(df, sub=None) -> pd.DataFrame:
    """Flag current rows: ddate = the filing's period end, taken
    from SUB when given (SOI's own period may be empty)."""
    df = df.copy()
    if sub is not None:
        per = df["adsh"].map(sub.set_index("adsh")["period"])
        df["period"] = per.fillna(df["period"])
    df["is_current"] = df["ddate"] == df["period"]
    return df


def coalesce_holdings(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (filing, date, identifier), first non-null value
    per field; n_conflicts counts fields whose values disagree."""
    rows = df[df["identifier"].notna()].copy()
    fields = [f for f in list(CANONICAL) + TEXT if f in rows]
    meta = [c for c in META if c in rows]
    g = rows.groupby(KEY, sort=False, dropna=False)
    out = g[meta + fields].first()
    out["source_rows"] = g["soi_row"].apply(
        lambda s: ";".join(map(str, s)))
    out["n_rows"] = g.size()
    out["n_conflicts"] = g[fields].nunique().gt(1).sum(axis=1)
    return out.reset_index()
