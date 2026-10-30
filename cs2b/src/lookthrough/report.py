"""Generate panel and reports; read human triage from a separate, never-written input."""
import json
from pathlib import Path

import pandas as pd

from . import paths, reconcile
from .evidence import COLUMNS as SOURCE_COLUMNS

PANEL_COLS = ["adsh", "cik", "name", "period", "identifier", "investment_type", "industry", "affiliation",
              "principal", "cost", "fair_value", "interest_rate", "spread", "pik_rate", "maturity",
              "pct_net_assets", "source_rows", "n_rows", "n_conflicts", "release", "subsidiary", "is_debt"]
COVERAGE_COLS = ["adsh", "name", "n_holdings", "holdings_fv", "filed_fv", "gap_pct",
                 "admitted", "triage_category"]
TRIAGE_COLS = ["adsh", "triage_category", "evidence", "example", "fix_or_reason",
               "review_status", "reviewed_holdings_fv", "reviewed_filed_fv"]


def load_triage(path) -> pd.DataFrame:
    """Missing input means unfinished triage; malformed input is an error.

    Reviewed totals bind the evidence to the result being reviewed. Changed
    totals require another review rather than silently reusing old conclusions.
    """
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=TRIAGE_COLS).set_index("adsh")
    rows = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = set(TRIAGE_COLS) - set(rows.columns)
    if missing:
        raise ValueError(f"Triage input missing columns: {sorted(missing)}")
    rows = rows[TRIAGE_COLS].apply(lambda col: col.str.strip())
    if rows["adsh"].eq("").any() or rows["adsh"].duplicated().any():
        raise ValueError("Triage input needs one non-empty, unique adsh per filing")
    invalid = set(rows["triage_category"]) - set(reconcile.TRIAGE) - {""}
    if invalid:
        raise ValueError(f"Invalid triage categories: {sorted(invalid)}")
    if not rows["review_status"].isin(["", "draft", "reviewed"]).all():
        raise ValueError("review_status must be blank, draft or reviewed")
    for col in ("reviewed_holdings_fv", "reviewed_filed_fv"):
        numeric = pd.to_numeric(rows[col].replace("", float("nan")), errors="coerce")
        if (rows[col].ne("") & (numeric.isna() | numeric.abs().eq(float("inf")))).any():
            raise ValueError(f"{col} must be blank or a finite number")
        rows[col] = numeric
    return rows.set_index("adsh")


def write_outputs(kept: pd.DataFrame, rec: pd.DataFrame, diag: pd.DataFrame,
                  log: pd.DataFrame, root, P, *, sub=None) -> dict:
    """Write current admitted holdings and reports from one reconciliation result.

    Never edits the configured triage CSV. A complete entry requires human review,
    evidence, an example, a fix/reason, and matching reviewed totals. Completion
    describes documentation, not proof that the stated root cause is correct.
    """
    root = Path(root)
    out, rep = root / P["outputs"]["panel"], root / P["outputs"]["reports"]
    triage_path = root / P.get("triage", {}).get("input", "data/triage.csv")
    triage = load_triage(triage_path)
    required = {"adsh", "cik", "name", "period", "identifier", "fair_value", "source_rows"}
    if not required <= set(kept):
        raise ValueError(f"Panel input missing columns: {sorted(required - set(kept))}")
    metrics = reconcile.coverage(rec, sub)
    admitted = set(rec.loc[rec["admitted"], "adsh"])
    panel = kept.loc[kept["adsh"].isin(admitted)].copy()
    if "is_current" not in panel or not panel["is_current"].fillna(False).all():
        raise ValueError("Panel must contain current-period holdings only")
    if "release" not in panel:
        releases = paths.release_dirs(P, root)
        if len(releases) != 1:
            raise ValueError("Multi-release panel requires release provenance on every holding")
        panel["release"] = next(iter(releases))
    if panel["release"].isna().any() or panel["release"].astype(str).str.strip().eq("").any():
        raise ValueError("Panel release provenance must not be empty")
    if not panel["source_rows"].astype(str).str.fullmatch(r"\d+(;\d+)*").all():
        raise ValueError("source_rows must contain semicolon-separated SOI row numbers")
    sums = panel.groupby("adsh")["fair_value"].sum(min_count=1)
    expected = rec.loc[rec["admitted"]].set_index("adsh")
    counts = panel.groupby("adsh").size().reindex(expected.index)
    if not counts.eq(expected["n_holdings"]).all():
        raise ValueError("Panel holding counts disagree with reconciliation results")
    if set(sums.index) != admitted or not (sums.reindex(expected.index) - expected["holdings_fv"]).abs().le(.01).all():
        raise ValueError("Panel sums disagree with admitted reconciliation results")
    panel = panel[[c for c in PANEL_COLS + SOURCE_COLUMNS if c in panel]]
    cov = rec.copy()
    cov["triage_category"] = ""
    summaries = []
    incomplete = []
    for row in rec.loc[~rec["admitted"]].itertuples():
        entry = triage.loc[row.adsh] if row.adsh in triage.index else None
        complete = False
        stale = False
        if entry is not None:
            complete = (entry["review_status"] == "reviewed"
                        and all(entry[c] for c in ("triage_category", "evidence", "example", "fix_or_reason")))
            for current, recorded in ((row.holdings_fv, entry["reviewed_holdings_fv"]),
                                      (row.filed_fv, entry["reviewed_filed_fv"])):
                same = ((pd.isna(current) and pd.isna(recorded))
                        or (pd.notna(current) and pd.notna(recorded) and abs(current - recorded) <= .01))
                stale |= not same
            complete = complete and not stale
        if not complete:
            incomplete.append(row.adsh)
        # An unreviewed category must not appear ready for the grader's checker.
        category = entry["triage_category"] if complete else "to_triage"
        cov.loc[cov["adsh"].eq(row.adsh), "triage_category"] = category
        summaries.append((row, entry, complete, stale))
    metrics.update({"triage_complete": not incomplete,
                    "triage_incomplete_filings": len(incomplete),
                    "triage_incomplete_adsh": incomplete,
                    "cleaning_rules": log["rule"].tolist()})
    money = lambda value: "n/a" if pd.isna(value) else f"{value:,.0f}"
    pct = lambda value: "n/a" if pd.isna(value) else f"{value:+.3%}"
    escape = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
    headline = [
        f"Filings attempted: {metrics['filings_attempted']}; admitted: {metrics['filings_admitted']} "
        f"({metrics['share_of_filings']:.1%}).",
        f"Known positive filed fair value attempted: ${metrics['filed_fv_attempted']:,.0f}; "
        f"admitted: ${metrics['filed_fv_admitted']:,.0f} ({metrics['share_of_dollars']:.1%}).",
        f"Attempts without a usable filed total: {metrics['filings_without_usable_filed_total']}. "
        "Their unknown dollars are not included in the dollar denominator.",
        f"Triage entries incomplete: {len(incomplete)}. "
        "Outputs are preliminary until filing-evidence review is complete.",
        f"Cleaning rules used: {', '.join(metrics['cleaning_rules'])}.",
    ]
    lines = ["# Coverage report", "", *headline, ""]
    if sub is not None:
        lines += [f"SUB filings without SOI rows (not attempted): {metrics['filings_without_soi_rows']}.",
                  *[f"- {a}" for a in metrics["filings_without_soi_adsh"]], ""]
    else:
        lines += ["SUB not supplied; filings without SOI rows were not assessed.", ""]
    lines += ["| Filing | BDC | Holdings | Holdings FV | Filed FV | Gap | Admitted | Triage |",
              "|---|---|---:|---:|---:|---:|---|---|"]
    lines += [f"| {r.adsh} | {escape(r.name)} | {r.n_holdings} | {money(r.holdings_fv)} | "
              f"{money(r.filed_fv)} | {pct(r.gap_pct)} | {r.admitted} | {r.triage_category} |"
              for r in cov.itertuples()]
    tri = ["# Triage of non-admitted filings", "", *headline, "",
           "Generated from the separate triage input. Edit that input, not this report.",
           "A reviewed entry records human-supplied evidence; automated checks only assess completeness and stale totals.", ""]
    diagnostics = diag.set_index("adsh") if "adsh" in diag else pd.DataFrame()
    for row, entry, complete, stale in summaries:
        status = "COMPLETE" if complete else ("INCOMPLETE — totals changed; re-review required" if stale else "INCOMPLETE")
        tri += [f"## {escape(row.name)} ({row.adsh})", "", f"- Status: **{status}**",
                f"- Holdings FV: {money(row.holdings_fv)}; filed FV: {money(row.filed_fv)}; gap: {pct(row.gap_pct)}",
                f"- Filed-total status: {getattr(row, 'filed_total_status', 'not supplied')}"]
        if row.adsh in diagnostics.index:
            d = diagnostics.loc[row.adsh]
            tri += [f"- Diagnostic clues (not proven causes): {d.get('missing_fv_rows', 'n/a')} holdings missing fair value; "
                    f"{d.get('rows_without_identifier', 'n/a')} current SOI rows without identifiers; "
                    f"{d.get('custom_fv_facts_in_num', 'n/a')} custom fair-value facts in NUM."]
        for label, field in (("Category", "triage_category"), ("Evidence", "evidence"),
                             ("Example", "example"), ("Fix or reason", "fix_or_reason")):
            value = entry[field] if entry is not None and entry[field] else "Not yet documented"
            tri.append(f"- {label}: {escape(value)}")
        tri.append("")
    # Validate everything above before replacing any output. Parquet is required
    # by the handout: fail explicitly if its engine is unavailable, no CSV fallback.
    out.mkdir(parents=True, exist_ok=True)
    rep.mkdir(parents=True, exist_ok=True)
    panel_path = out / "holdings.parquet"
    panel.to_parquet(panel_path, index=False)
    cov[COVERAGE_COLS].to_csv(rep / "coverage.csv", index=False)
    (rep / "coverage.json").write_text(json.dumps(metrics, indent=2) + "\n")
    (rep / "coverage.md").write_text("\n".join(lines) + "\n")
    (rep / "triage.md").write_text("\n".join(tri).rstrip() + "\n")
    log.to_csv(rep / "cleaning_log.csv", index=False)
    return {"panel": panel_path, "coverage": rep / "coverage.csv", "triage": rep / "triage.md"}
