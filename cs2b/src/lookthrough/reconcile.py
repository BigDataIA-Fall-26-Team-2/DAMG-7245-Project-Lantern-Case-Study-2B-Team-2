"""Reconcile holdings to each filing's own reported total."""
import math

import pandas as pd

from .mapping import parse_segments

FV_TAG = "InvestmentOwnedAtFairValue"
# allowed values of triage_category in coverage.csv (Case Study 2B, Section 7)
TRIAGE = ("comparative_leakage", "totals_counted", "cash_lines",
          "restated_copies", "unfunded_commitments", "custom_tags",
          "no_identified_holdings", "affiliate_split", "no_filed_total",
          "other")


def filed_totals(num, sub) -> pd.DataFrame:
    """Select a unique, finite USD instant total at the SUB period end.

    Identical duplicate facts are harmless. Conflicting values remain unresolved
    (filed_fv is missing), rather than choosing whichever total admits a filing.
    Keep a status and candidate count so exclusions can be explained downstream.
    """
    f = num[(num["tag"] == FV_TAG) & (num["dimn"] == "0")
            & (num["uom"] == "USD") & (num["qtrs"] == "0")].copy()
    f = f.merge(sub[["adsh", "period"]], on="adsh", validate="many_to_one")
    f = f[f["ddate"] == f["period"]].copy()
    f["value"] = pd.to_numeric(f["value"], errors="coerce")
    f["invalid"] = ~f["value"].map(lambda value: pd.notna(value) and math.isfinite(value))
    totals = f.groupby("adsh", as_index=False).agg(
        filed_fv=("value", "first"),
        filed_total_candidates=("value", "nunique"),
        invalid_total=("invalid", "any"))
    totals["filed_total_status"] = "ok"
    totals.loc[totals["filed_total_candidates"].gt(1), "filed_total_status"] = "conflicting"
    totals.loc[totals["invalid_total"], "filed_total_status"] = "invalid"
    totals.loc[totals["filed_total_status"].eq("ok") & totals["filed_fv"].le(0),
               "filed_total_status"] = "nonpositive"
    unresolved = totals["filed_total_status"].isin(["conflicting", "invalid"])
    totals.loc[unresolved, "filed_fv"] = float("nan")
    return totals.drop(columns="invalid_total")


def reconcile(current, filed, sub, tolerance,
              soi_adsh=None) -> pd.DataFrame:
    """One row per filing attempted: every current filing with SOI
    rows (soi_adsh), even one with no identifiable holdings."""
    if not math.isfinite(tolerance) or not 0 <= tolerance < 1:
        raise ValueError("tolerance must be a finite fraction in [0, 1)")
    current = current.copy()
    current["fair_value"] = pd.to_numeric(current["fair_value"], errors="coerce")
    finite = current["fair_value"].map(lambda value: pd.notna(value) and math.isfinite(value))
    current["invalid_fv"] = current["fair_value"].notna() & ~finite
    current.loc[~finite, "fair_value"] = float("nan")
    agg = current.groupby("adsh", as_index=False).agg(
        n_holdings=("identifier", "size"),
        holdings_fv=("fair_value", lambda values: values.sum(min_count=1)),
        missing_fv=("fair_value", lambda values: int(values.isna().sum())),
        invalid_fv=("invalid_fv", "sum"))
    ids = set(agg["adsh"]) if soi_adsh is None else set(soi_adsh)
    cols = ["adsh", "cik", "name", "form", "period"]
    r = (sub.loc[sub["adsh"].isin(ids), cols]
         .merge(agg, on="adsh", how="left", validate="one_to_one")
         .merge(filed, on="adsh", how="left", validate="one_to_one"))
    for c in ("n_holdings", "missing_fv", "invalid_fv"):
        r[c] = r[c].fillna(0).astype(int)
    if "filed_total_status" not in r:
        r["filed_total_status"] = "ok"
    r["filed_total_status"] = r["filed_total_status"].fillna("missing")
    r.loc[r["filed_fv"].isna() & r["filed_total_status"].eq("ok"),
          "filed_total_status"] = "missing"
    # A percentage gap is undefined for absent/nonpositive/nonfinite totals,
    # no holdings, all-missing holding values, or malformed infinite values.
    valid = (r["filed_fv"].map(lambda value: pd.notna(value) and math.isfinite(value)) & r["filed_fv"].gt(0)
             & r["holdings_fv"].map(lambda value: pd.notna(value) and math.isfinite(value)) & r["n_holdings"].gt(0)
             & r["invalid_fv"].eq(0) & r["filed_total_status"].eq("ok"))
    r["gap_pct"] = float("nan")
    r.loc[valid, "gap_pct"] = ((r.loc[valid, "holdings_fv"] - r.loc[valid, "filed_fv"])
                               / r.loc[valid, "filed_fv"])
    r["admitted"] = valid & r["gap_pct"].abs().le(tolerance)
    return r.sort_values("holdings_fv", ascending=False,
                         na_position="last").reset_index(drop=True)


def coverage(rec: pd.DataFrame, sub=None) -> dict:
    """Shares of filings and of filed dollars admitted."""
    a = rec[rec["admitted"]]
    if rec["adsh"].duplicated().any():
        raise ValueError("Coverage requires one row per attempted filing")
    known = rec["filed_fv"].map(lambda value: pd.notna(value) and math.isfinite(value)) & rec["filed_fv"].gt(0)
    total = rec.loc[known, "filed_fv"].sum()
    got = float(a["filed_fv"].sum())
    n = len(rec)
    out = {"filings_attempted": int(n),
           "filings_admitted": int(len(a)),
           "share_of_filings": round(len(a) / n, 3) if n else 0.0,
           "filings_without_usable_filed_total": int((~known).sum()),
           "filed_fv_attempted": float(total),
           "filed_fv_admitted": got,
           "share_of_dollars":
               round(float(got / total), 3) if total else 0.0}
    if sub is not None:
        absent = sorted(set(sub["adsh"]) - set(rec["adsh"]))
        out["filings_without_soi_rows"] = len(absent)
        out["filings_without_soi_adsh"] = absent
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
            "filed_total_status": getattr(r, "filed_total_status", "missing" if pd.isna(r.filed_fv) else "ok"),
        })
    return pd.DataFrame(rows)
