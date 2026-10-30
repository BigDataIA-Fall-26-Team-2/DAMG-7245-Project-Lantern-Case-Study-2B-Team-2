"""Optional affiliation-category comparison, with explicit incomplete cases."""

import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import affiliation, paths

P = paths.load_params(ROOT)
work = ROOT / "outputs/work"
kept = pd.read_parquet(work / "kept.parquet")
kept["affiliation_member"] = affiliation.source_members(
    kept, paths.release_dirs(P, ROOT)
)
result = affiliation.reconcile_affiliations(
    kept,
    pd.read_parquet(work / "num.parquet"),
    pd.read_parquet(work / "sub.parquet"),
    P["reconcile"]["tolerance"],
)
rep = ROOT / P["outputs"]["reports"]
result.to_csv(rep / "affiliation.csv", index=False)
complete = result[~result.status.eq("incomplete_classification_or_values")]
lines = [
    "# Affiliation reconciliation (stretch)",
    "",
    "Compares cleaned holdings with current USD instant InvestmentOwnedAtFairValue NUM facts whose sole dimension is InvestmentIssuerAffiliationAxis.",
    "Holding membership comes only from standard affiliation enumeration facts on the holding’s own SOI source rows. No name guessing or forward filling.",
    "",
    f"{len(result)} reported category totals across {result.adsh.nunique()} filings. Status counts: {result.status.value_counts().to_dict()}.",
    "Unclassified holdings prevent a category pass. Identical duplicate totals are accepted; conflicting totals are unusable. Missing reported categories are not invented.",
    "This optional comparison does not alter the overall filing admission decision.",
    "",
    "| Filing | Category | Holdings FV | Filed category FV | Result |",
    "|---|---|---:|---:|---|",
]
for row in complete.itertuples():
    lines.append(
        f"| {row.adsh} | {row.affiliation} | {row.holdings_fv:,.2f} | {row.filed_category_fv:,.2f} | {row.status} |"
    )
lines += [
    "",
    "All results, including incomplete classifications and SOI row provenance, are in `affiliation.csv`. Raw references are in the selected release’s `datasets/num.tsv`; match accession, SUB period, tag, member, USD, qtrs=0, dimn=1.",
    "Reproduce with `python scripts/affiliation.py` or `dvc repro affiliation`.",
]
(rep / "affiliation.md").write_text("\n".join(lines) + "\n")
print(result.status.value_counts().to_dict())
