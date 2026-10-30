"""Independently audit saved exclusion decisions against raw SOI and NUM.

Run after dvc repro: python tools/review_triage.py. Writes audit evidence only;
never changes review status or claims unresolved root causes have been found.
"""

from pathlib import Path
import sys
import pandas as pd

r = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(r / "src"))
from lookthrough import load, mapping, combine, reconcile, paths

P = paths.load_params(r)
dirs = paths.release_dirs(P, r)
sub = pd.read_parquet(r / "outputs/work/sub.parquet").set_index("adsh")
k = pd.read_parquet(r / "outputs/work/kept.parquet")
rec = pd.read_parquet(r / "outputs/work/rec.parquet").set_index("adsh")
notes = pd.read_csv(r / "data/triage.csv", keep_default_na=False).set_index("adsh")
tags = combine.load_tag_all(dirs)
raws = {}
nums = {}
results = []
for release, d in dirs.items():
    if not combine.has_soi(d):
        continue
    cmap = mapping.map_soi_columns(load.soi_header(d), tags)
    cols = ["adsh", "ddate", mapping.AXES["identifier"], *cmap["fair_value"]]
    raw = pd.read_csv(d / "soi.tsv", sep="\t", dtype=str, usecols=lambda c: c in cols)
    raw["ddate"] = load.norm_date(raw.ddate)
    raw["fv"] = float("nan")
    for c in cmap["fair_value"]:
        raw["fv"] = raw.fv.fillna(pd.to_numeric(raw[c], errors="coerce"))
    raws[release] = raw
    ids = set(notes.index[sub.loc[notes.index, "release"].eq(release)])
    if ids:
        nums[release] = load.load_num(d, tags=[reconcile.FV_TAG], adsh=ids)
for a, note in notes.iterrows():
    s = sub.loc[a]
    v = rec.loc[a]
    h = k[k.adsh.eq(a)]
    raw = raws[s.release]
    n = nums[s.release]
    nf = n[
        n.adsh.eq(a)
        & n.ddate.eq(s.period)
        & n.tag.eq(reconcile.FV_TAG)
        & n.dimn.eq("0")
        & n.qtrs.eq("0")
        & n.uom.eq("USD")
    ]
    values = nf.value.dropna().unique()
    if pd.notna(v.filed_fv):
        assert len(values) == 1 and abs(values[0] - v.filed_fv) < 0.01, (
            a,
            values,
            v.filed_fv,
        )
    else:
        assert len(nf) == 0, (a, "unresolved reference needs further audit")
    for row in h.itertuples():
        rawrows = raw.loc[[int(i) for i in row.source_rows.split(";")]]
        assert rawrows.adsh.eq(a).all() and rawrows.ddate.eq(s.period).all(), (
            a,
            "provenance",
        )
        if pd.notna(row.fair_value):
            assert rawrows.fv.sub(row.fair_value).abs().le(0.01).any(), (
                a,
                row.identifier,
                "amount changed",
            )
        else:
            assert rawrows.fv.isna().all(), (a, row.identifier, "missed mapped value")
    if len(h):
        assert abs(h.fair_value.sum(min_count=1) - v.holdings_fv) < 0.01, (a, "sum")
    assert not v.admitted
    if pd.notna(v.gap_pct):
        assert abs(v.gap_pct) > P["reconcile"]["tolerance"]
    finite = h[h.fair_value.notna()]
    example = finite.loc[finite.fair_value.abs().idxmax()] if len(finite) else None
    missing = h[h.fair_value.isna()]
    row = dict(
        adsh=a,
        release=s.release,
        period=s.period,
        n_holdings=len(h),
        source_rows_checked=sum(len(x.split(";")) for x in h.source_rows),
        missing_fv=int(h.fair_value.isna().sum()),
        holdings_fv=v.holdings_fv,
        filed_fv=v.filed_fv,
        gap_pct=v.gap_pct,
        raw_total_fact_count=len(nf),
        trace_verified=True,
        missing_example_rows=missing.iloc[0].source_rows if len(missing) else "",
        example_rows=example.source_rows if example is not None else "",
        example_identifier=example.identifier if example is not None else "",
        example_fv=example.fair_value if example is not None else None,
        filing_url=s.inlineurl,
    )
    if note.triage_category == "unfunded_commitments":
        typed = n[
            n.adsh.eq(a)
            & n.ddate.eq(s.period)
            & n.dimn.eq("1")
            & n.qtrs.eq("0")
            & n.uom.eq("USD")
            & n.value.lt(0)
        ].copy()
        typed = typed[
            typed.segments.map(
                lambda x: set(mapping.parse_segments(x)) == {"InvestmentTypeAxis"}
            )
        ]
        row["negative_type_fv"] = float(typed.value.sum())
        assert abs(v.holdings_fv + typed.value.sum() - v.filed_fv) < 0.01
    results.append(row)
pd.DataFrame(results).to_csv(r / "reports/triage_review_audit.csv", index=False)
print(
    "Verified exclusions",
    len(results),
    "source references",
    sum(x["source_rows_checked"] for x in results),
)
print("Type-adjustment explanations", [x for x in results if "negative_type_fv" in x])
