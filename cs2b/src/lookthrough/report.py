"""Write the Case Study 2B outputs: the panel, coverage, triage and cleaning log."""
import json

import pandas as pd

from . import reconcile, tables

PANEL_COLS = ["adsh", "cik", "name", "period", "identifier", "investment_type", "industry", "affiliation",
              "principal", "cost", "fair_value", "interest_rate", "spread", "pik_rate", "maturity",
              "pct_net_assets", "source_rows", "n_rows", "n_conflicts"]


def write_outputs(kept: pd.DataFrame, rec: pd.DataFrame, diag: pd.DataFrame, log: pd.DataFrame, root, P) -> dict:
    out = root / P["outputs"]["panel"]; rep = root / P["outputs"]["reports"]
    rep.mkdir(parents=True, exist_ok=True)
    admitted = set(rec.loc[rec["admitted"], "adsh"])
    panel = kept[kept["adsh"].isin(admitted)][[c for c in PANEL_COLS if c in kept]]
    panel_path = tables.save_table(panel, out / "holdings")
    cov = rec.copy()
    cov["triage_category"] = ["" if a else "to_triage" for a in cov["admitted"]]
    cov.to_csv(rep / "coverage.csv", index=False)
    (rep / "coverage.json").write_text(json.dumps(reconcile.coverage(rec), indent=2))   # DVC metric
    a = cov[cov["admitted"]]
    lines = ["# Coverage report", "",
             f"Filings attempted: {len(cov)}; admitted: {len(a)} ({len(a) / max(len(cov), 1):.0%}).",
             f"Filed fair value attempted: ${cov['filed_fv'].sum():,.0f}; admitted: ${a['filed_fv'].sum():,.0f} "
             f"({a['filed_fv'].sum() / max(cov['filed_fv'].sum(), 1):.0%}).", "",
             "| BDC | Holdings | Holdings FV | Filed FV | Gap | Admitted |", "|---|---:|---:|---:|---:|---|"]
    money = lambda x: "n/a" if pd.isna(x) else f"{x:,.0f}"
    pct = lambda x: "n/a" if pd.isna(x) else f"{x:+.2%}"
    lines += [f"| {r.name} | {r.n_holdings} | {money(r.holdings_fv)} | {money(r.filed_fv)} | {pct(r.gap_pct)} | {r.admitted} |"
              for r in cov.itertuples()]
    (rep / "coverage.md").write_text("\n".join(lines) + "\n")
    tri = ["# Triage of non-admitted filings", "",
           "For each filing: the evidence, the root-cause category, an example (accession number and SOI row), and the fix you applied or why none is possible.", ""]
    for r in diag.itertuples():
        tri += [f"## {r.name} ({r.adsh})", "", f"- Gap: {pct(r.gap_pct)}",
                f"- Holdings identified: {r.n_holdings}; current SOI rows without an identifier: {r.rows_without_identifier}",
                f"- Holdings with missing fair value: {r.missing_fv_rows}",
                f"- No filed total in NUM: {r.no_filed_total}",
                f"- Custom tag used in the SOI: {r.custom_tag_in_soi}; custom fair-value facts in NUM: {r.custom_fv_facts_in_num}",
                f"- Negative fair value tagged by investment type in NUM: {r.negative_type_level_fv:,.0f}",
                "- **Root-cause category:** _to fill in_", "- **Example:** _to fill in_", "- **Fix or reason:** _to fill in_", ""]
    (rep / "triage.md").write_text("\n".join(tri))
    log.to_csv(rep / "cleaning_log.csv", index=False)
    return {"panel": panel_path, "coverage": rep / "coverage.csv", "triage": rep / "triage.md"}
