"""Optional category-level reconciliation; never changes filing admission."""

import re
import pandas as pd
from .mapping import parse_segments
from .load import norm_date
from .reconcile import FV_TAG

AXIS = "InvestmentIssuerAffiliationAxis"
ENUM = "Investment, Issuer Affiliation [Extensible Enumeration]"
MEMBERS = {
    "InvestmentUnaffiliatedIssuerMember": "unaffiliated",
    "InvestmentAffiliatedIssuerControlledMember": "controlled affiliate",
    "InvestmentAffiliatedIssuerNoncontrolledMember": "noncontrolled affiliate",
}


def source_members(kept, dirs):
    """Map only explicit standard enumeration facts on the holding's own rows.

    No name inference, forward filling, or guessed membership for unlabelled rows.
    Conflicting labels and custom members remain unclassified.
    """
    sources = {}
    for release in kept.release.unique():
        raw = pd.read_csv(
            dirs[release] / "soi.tsv",
            sep="\t",
            dtype=str,
            usecols=lambda c: c in ("adsh", "ddate", ENUM),
        )
        raw["ddate"] = norm_date(raw["ddate"])
        sources[release] = raw
    result = []
    for row in kept.itertuples():
        raw = sources[row.release].loc[[int(i) for i in row.source_rows.split(";")]]
        if not raw.adsh.eq(row.adsh).all() or not raw.ddate.eq(row.period).all():
            raise ValueError("Affiliation source provenance does not match filing")
        labels = set(raw[ENUM].dropna()) if ENUM in raw else set()
        members = set()
        for label in labels:
            match = re.fullmatch(r"https?://fasb.org/us-gaap/\d{4}#([^\s]+)", label)
            members.add(match[1] if match and match[1] in MEMBERS else None)
        result.append(next(iter(members)) if len(members) == 1 else None)
    return pd.Series(result, index=kept.index, dtype="object")


def reconcile_affiliations(kept, num, sub, tolerance):
    """Compare complete classified holdings with unique current category totals.

    Unknown membership anywhere in a filing prevents any category being called
    matched: those holdings could belong to it. Missing category values also
    prevent a pass. Missing categories are not inferred from the overall total.
    """
    periods = sub.set_index("adsh").period
    f = num[
        num.tag.eq(FV_TAG)
        & num.qtrs.eq("0")
        & num.uom.eq("USD")
        & num.dimn.eq("1")
        & num.ddate.eq(num.adsh.map(periods))
    ].copy()
    dims = f.segments.map(parse_segments)
    f["member"] = dims.map(lambda d: d.get(AXIS) if set(d) == {AXIS} else None)
    f = f[f.member.isin(MEMBERS)]
    rows = []
    for (adsh, member), facts in f.groupby(["adsh", "member"], sort=True):
        h = kept[kept.adsh.eq(adsh)]
        group = h[h.affiliation_member.eq(member)]
        unknown = int(h.affiliation_member.isna().sum())
        values = pd.to_numeric(facts.value, errors="coerce")
        valid = values.notna().all() and values.abs().lt(float("inf")).all()
        reference = (
            float(values.iloc[0]) if valid and values.nunique() == 1 else float("nan")
        )
        total = float(group.fair_value.sum(min_count=1)) if len(group) else 0.0
        gap = (total - reference) / reference if reference > 0 else float("nan")
        status = (
            "matched"
            if (abs(gap) <= tolerance if reference > 0 else total == reference == 0)
            else "mismatch"
        )
        if pd.isna(reference) or reference < 0:
            status = "unusable_category_total"
        elif not len(h) or unknown or group.fair_value.isna().any():
            status = "incomplete_classification_or_values"
        rows.append(
            dict(
                adsh=adsh,
                period=periods[adsh],
                affiliation=MEMBERS[member],
                member=member,
                n_holdings=len(group),
                unclassified_holdings=unknown,
                holdings_fv=total,
                filed_category_fv=reference,
                gap_pct=gap,
                num_fact_count=len(facts),
                status=status,
                source_rows=";".join(group.source_rows),
            )
        )
    return pd.DataFrame(
        rows,
        columns=[
            "adsh",
            "period",
            "affiliation",
            "member",
            "n_holdings",
            "unclassified_holdings",
            "holdings_fv",
            "filed_category_fv",
            "gap_pct",
            "num_fact_count",
            "status",
            "source_rows",
        ],
    )
