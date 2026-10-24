"""Reconcile holdings to each filing's own reported total."""
import pandas as pd

from .mapping import parse_segments

FV_TAG = "InvestmentOwnedAtFairValue"
# allowed values of triage_category in coverage.csv (Case Study 2B, Section 7)
TRIAGE = ("comparative_leakage", "totals_counted", "cash_lines",
          "restated_copies", "unfunded_commitments", "custom_tags",
          "no_identified_holdings", "affiliate_split", "no_filed_total",
          "other")


def filed_totals(num, sub) -> pd.DataFrame:
    """The undimensioned fair-value fact at each period end."""
    f = num[(num["tag"] == FV_TAG) & (num["dimn"] == "0")]
    f = f.merge(sub[["adsh", "period"]], on="adsh")
    f = f[f["ddate"] == f["period"]]
    return (f.groupby("adsh", as_index=False)["value"].max()
            .rename(columns={"value": "filed_fv"}))


def reconcile(current, filed, sub, tolerance,
              soi_adsh=None) -> pd.DataFrame:
    """One row per filing attempted: every current filing with SOI
    rows (soi_adsh), even one with no identifiable holdings."""
    agg = current.groupby("adsh", as_index=False).agg(
        n_holdings=("identifier", "size"),
        holdings_fv=("fair_value", "sum"),
        missing_fv=("fair_value", lambda s: int(s.isna().sum())))
    ids = set(agg["adsh"]) if soi_adsh is None else set(soi_adsh)
    cols = ["adsh", "cik", "name", "form", "period"]
    r = (sub.loc[sub["adsh"].isin(ids), cols]
         .merge(agg, on="adsh", how="left")
         .merge(filed, on="adsh", how="left"))
    for c in ("n_holdings", "missing_fv"):
        r[c] = r[c].fillna(0).astype(int)
    r["gap_pct"] = (r["holdings_fv"] - r["filed_fv"]) / r["filed_fv"]
    r["admitted"] = (r["gap_pct"].abs().le(tolerance)
                     & r["filed_fv"].notna() & r["n_holdings"].gt(0))
    return r.sort_values("holdings_fv", ascending=False,
                         na_position="last").reset_index(drop=True)


def coverage(rec: pd.DataFrame, sub=None) -> dict:
    """Shares of filings and of filed dollars admitted."""
    a = rec[rec["admitted"]]
    total = rec["filed_fv"].sum()
    got = float(a["filed_fv"].sum())
    n = len(rec)
    out = {"filings_attempted": int(n),
           "filings_admitted": int(len(a)),
           "share_of_filings": round(len(a) / n, 3) if n else 0.0,
           "filed_fv_attempted": float(total),
           "filed_fv_admitted": got,
           "share_of_dollars":
               round(float(got / total), 3) if total else 0.0}
    if sub is not None:
        out["filings_without_soi_rows"] = int(len(sub) - n)
    return out


def diagnose(rec, current, num, canon=None) -> pd.DataFrame:
    """Evidence for triaging each non-admitted filing."""
    rows = []
    for r in rec[~rec["admitted"]].itertuples():
        h = current[current["adsh"] == r.adsh]
        n = num[(num["adsh"] == r.adsh) & (num["ddate"] == r.period)]
        typed = n[(n["tag"] == FV_TAG) & (n["dimn"] == "1")]
        by_type = typed["segments"].map(
            lambda s: "InvestmentTypeAxis" in parse_segments(s))
        neg = typed[(typed["value"] < 0) & by_type]
        no_id = 0
        if canon is not None:
            c = canon[(canon["adsh"] == r.adsh) & canon["is_current"]]
            no_id = int(c["identifier"].isna().sum())
        cstm = bool((h["cstm"] == "1").any()) if len(h) else False
        rows.append({
            "adsh": r.adsh, "name": r.name, "gap_pct": r.gap_pct,
            "n_holdings": int(r.n_holdings),
            "rows_without_identifier": no_id,
            "missing_fv_rows": int(h["fair_value"].isna().sum()),
            "custom_tag_in_soi": cstm,
            "custom_fv_facts_in_num": int((n["version"] == r.adsh).sum()),
            "negative_type_level_fv": float(neg["value"].sum()),
            "no_filed_total": bool(pd.isna(r.filed_fv)),
        })
    return pd.DataFrame(rows)
