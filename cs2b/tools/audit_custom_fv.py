"""Counterfactual custom-FV recovery audit. Never modifies pipeline holdings.

Compare current identifier-level custom NUM facts with missing SOI fair values,
then run the existing cleaning/reconciliation on a copy. A matched name alone
is not permission to recover a value: roll-forwards and commitments can repeat
or describe different amounts. No admission target is used to select a fact.
"""

import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import mapping, clean, pipeline, paths, reconcile

P = paths.load_params(ROOT)
work = ROOT / "outputs/work"
sub = pd.read_parquet(work / "sub.parquet")
num = pd.read_parquet(work / "num.parquet")
h = pd.read_parquet(work / "holdings.parquet")
before = pd.read_parquet(work / "rec.parquet").set_index("adsh")
periods = sub.set_index("adsh").period
facts = num[
    num.version.eq(num.adsh)
    & num.qtrs.eq("0")
    & num.uom.eq("USD")
    & num.ddate.eq(num.adsh.map(periods))
].copy()
facts["dims"] = facts.segments.map(mapping.parse_segments)
facts = facts[facts.dims.map(lambda d: "InvestmentIdentifierAxis" in d)].copy()
facts["identifier"] = facts.dims.map(lambda d: d["InvestmentIdentifierAxis"])
# These are investigation candidates, NOT approved production mappings.
candidates = {
    "InvestmentOwnedFairValueBalance",
    "InvestmentOwnedFairValueEndingBalance",
    "InvestmentOwnedFairValueNetOfUnamortizedFees",
}
counts = (
    facts.groupby("tag")
    .agg(facts=("tag", "size"), filings=("adsh", "nunique"))
    .reset_index()
)
counts["decision"] = counts.tag.map(
    lambda t: (
        "inspect scope; not approved for recovery"
        if t in candidates
        else "commitment/support or cash/money-market concept; not holding FV"
    )
)
counts.to_csv(ROOT / "reports/custom_tag_screen.csv", index=False)
lookup = {}
for key, g in facts[facts.tag.isin(candidates)].groupby(
    ["release", "adsh", "identifier"]
):
    values = g.value.dropna().unique()
    # Multiple dimensions or multiple conflicting values require context inspection.
    if (
        len(values) == 1
        and g.dims.map(lambda d: set(d) == {"InvestmentIdentifierAxis"}).all()
    ):
        lookup[key] = (float(values[0]), ";".join(sorted(set(g.tag))))
changed = h.copy()
matches = []
for i, row in h[h.is_current & h.fair_value.isna()].iterrows():
    match = lookup.get((row.release, row.adsh, row.identifier))
    if match:
        value, tag = match
        changed.at[i, "fair_value"] = value
        matches.append(
            dict(
                adsh=row.adsh,
                release=row.release,
                identifier=row.identifier,
                source_rows=row.source_rows,
                tag=tag,
                candidate_fv=value,
            )
        )
kept, _ = clean.apply_rules(changed[changed.is_current], pipeline.configured_rules(P))
after = reconcile.reconcile(
    kept,
    reconcile.filed_totals(num, sub),
    sub,
    P["reconcile"]["tolerance"],
    soi_adsh=set(before.index),
).set_index("adsh")
rows = []
for a in sorted({m["adsh"] for m in matches}):
    selected = [m for m in matches if m["adsh"] == a]
    rows.append(
        dict(
            adsh=a,
            matched_missing_holdings=len(selected),
            candidate_fv=sum(m["candidate_fv"] for m in selected),
            before_gap=before.loc[a, "gap_pct"],
            counterfactual_gap=after.loc[a, "gap_pct"],
            before_admitted=bool(before.loc[a, "admitted"]),
            counterfactual_admitted=bool(after.loc[a, "admitted"]),
        )
    )
pd.DataFrame(matches).to_csv(ROOT / "reports/custom_tag_candidates.csv", index=False)
pd.DataFrame(rows).to_csv(ROOT / "reports/custom_tag_counterfactual.csv", index=False)
new = [
    a for a in after.index if after.loc[a, "admitted"] and not before.loc[a, "admitted"]
]
lines = [
    "# Custom-tag recovery audit (stretch investigation)",
    "",
    f"Screened {len(facts)} current-period USD instant custom NUM facts on InvestmentIdentifierAxis, across {facts.adsh.nunique()} filings.",
    f"Exact identifier/context candidates fill {len(matches)} missing current holding values in a COPY of the inputs. Existing configured rules are then rerun. Newly admitted filings: {len(new)}.",
    "The production panel is unchanged. These candidates are not approved recovery mappings. The source investigation in docs/cleaning_log.md identifies the matching TCW facts as affiliate roll-forward ending balances, not additional schedule positions.",
    "",
    "| Filing | Missing holdings matched | Candidate FV | Before gap | Counterfactual gap | Newly admitted? |",
    "|---|---:|---:|---:|---:|---|",
]
for row in rows:
    lines.append(
        f"| {row['adsh']} | {row['matched_missing_holdings']} | {row['candidate_fv']:,.2f} | {row['before_gap']:+.3%} | {row['counterfactual_gap']:+.3%} | {row['counterfactual_admitted'] and not row['before_admitted']} |"
    )
lines += [
    "",
    "Cash/commitment/support tags cannot be substituted for investment fair value. Blue Owl fee-netted values concern holdings with an existing fair value; Goldman Sachs roll-forward identifiers do not match missing schedule holdings. Alternate standard `Investments` values are not custom-tag recovery and include subtotals.",
    "Result: no verified custom-tag recovery/re-admission has been established for these releases. Do not claim the two bonus points as completed. A new source-supported mapping or different candidate is required; tests or a desired total cannot supply that evidence.",
    "Reproduce: `python tools/audit_custom_fv.py` after `dvc repro`. See custom_tag_screen.csv, custom_tag_candidates.csv, custom_tag_counterfactual.csv and the existing source investigation for traceable details.",
]
(ROOT / "reports/custom_tag_recovery.md").write_text("\n".join(lines) + "\n")
print("candidate fills", len(matches), "new admissions", len(new))
print(rows)
