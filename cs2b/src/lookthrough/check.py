"""Validate Part 3 outputs against the configured releases and saved triage.

Run from cs2b: PYTHONPATH=src python -m lookthrough.check
The ten checks retain the starter's intent, with multi-release provenance and
explicit missing-value checks. This is not human verification of filing evidence.
"""
import re
import sys

import numpy as np
import pandas as pd

from . import combine, paths, reconcile, report, tables


def _numbers_match(actual, expected, atol):
    """Compare numeric arrays, allowing missing only when both sides are missing."""
    return np.isclose(np.asarray(actual, dtype=float), np.asarray(expected, dtype=float),
                      rtol=0, atol=atol, equal_nan=True)


def run_checks(root=None, sample=25) -> list:
    root = paths.repo_root(root)
    params = paths.load_params(root)
    dirs = paths.release_dirs(params, root)
    tol = float(params["reconcile"]["tolerance"])
    inputs = combine.load_inputs(dirs, num_tags=[reconcile.FV_TAG])
    sub, soi = inputs["sub"], inputs["canon"]
    filed = reconcile.filed_totals(inputs["num"], sub).set_index("adsh")["filed_fv"]
    hold = tables.load_table(root / params["outputs"]["panel"] / "holdings")
    cov = pd.read_csv(root / params["outputs"]["reports"] / "coverage.csv", dtype={"adsh": str})
    res = []

    def chk(name, ok, detail=""):
        res.append((name, bool(ok), detail))

    need = ["adsh", "cik", "name", "period", "identifier", "fair_value", "source_rows"]
    if len(dirs) > 1:
        need.append("release")
    chk("holdings has the required columns", all(c in hold for c in need),
        str([c for c in need if c not in hold]))
    need_c = report.COVERAGE_COLS
    chk("coverage.csv has the required columns", all(c in cov for c in need_c),
        str([c for c in need_c if c not in cov]))
    if not all(c in hold for c in need) or not all(c in cov for c in need_c):
        return res
    if "release" not in hold:
        hold["release"] = next(iter(dirs))  # legacy single-release panel
    boolean_text = cov["admitted"].astype(str).str.lower()
    valid_boolean = boolean_text.isin(["true", "false", "1", "0"])
    cov["admitted"] = boolean_text.isin(["true", "1"])
    expected = set(soi["adsh"]) & set(sub["adsh"])
    dropped, extra = expected - set(cov["adsh"]), set(cov["adsh"]) - expected
    chk("every filing with SOI rows is in coverage.csv (none dropped)",
        not dropped and not extra and not cov["adsh"].duplicated().any(),
        f"{len(dropped)} missing, {len(extra)} unexpected; duplicate rows: {cov['adsh'].duplicated().sum()}")
    target_totals = cov["adsh"].map(filed)
    total_ok = _numbers_match(cov["filed_fv"], target_totals, 1.0)
    chk("filed totals match NUM", total_ok.all(), f"{int((~total_ok).sum())} mismatched")
    adm = cov[cov["admitted"]]
    sums = hold.groupby("adsh")["fair_value"].sum(min_count=1)
    counts = hold.groupby("adsh").size()
    sum_ok = _numbers_match(adm["adsh"].map(sums), adm["holdings_fv"], 1.0)
    count_ok = adm["adsh"].map(counts).eq(adm["n_holdings"])
    chk("holdings sum to the reported holdings_fv", sum_ok.all() and count_ok.all(),
        f"{int((~sum_ok).sum())} sum mismatches; {int((~count_ok).sum())} count mismatches")
    usable = (np.isfinite(cov["filed_fv"]) & cov["filed_fv"].gt(0)
              & np.isfinite(cov["holdings_fv"]) & cov["n_holdings"].gt(0))
    expected_gap = pd.Series(float("nan"), index=cov.index)
    expected_gap.loc[usable] = ((cov.loc[usable, "holdings_fv"] - cov.loc[usable, "filed_fv"])
                                / cov.loc[usable, "filed_fv"])
    gap_ok = _numbers_match(cov["gap_pct"], expected_gap, 1e-12)
    chk("gap_pct is computed correctly", gap_ok.all(), f"{int((~gap_ok).sum())} wrong")
    # Use the freshly computed gap, not a potentially edited output gap.
    expected_admission = usable & expected_gap.abs().le(tol)
    admission_ok = expected_admission.eq(cov["admitted"]) & valid_boolean
    chk(f"admission follows the tolerance ({tol:.2%})", admission_ok.all(),
        f"{int((~admission_ok).sum())} inconsistent")
    cats = cov.loc[~cov["admitted"], "triage_category"].fillna("")
    bad_cat = sorted(set(cats) - set(reconcile.TRIAGE))
    triage_errors = []
    try:
        triage = report.load_triage(root / params.get("triage", {}).get("input", "data/triage.csv"))
        for row in cov.loc[~cov["admitted"]].itertuples():
            if row.adsh not in triage.index:
                triage_errors.append(row.adsh)
                continue
            note = triage.loc[row.adsh]
            complete = (note["review_status"] == "reviewed"
                        and all(note[c] for c in ("triage_category", "evidence", "example", "fix_or_reason"))
                        and note["triage_category"] == row.triage_category)
            current = [row.holdings_fv, row.filed_fv]
            reviewed = [note["reviewed_holdings_fv"], note["reviewed_filed_fv"]]
            if not complete or not _numbers_match(current, reviewed, .01).all():
                triage_errors.append(row.adsh)
    except ValueError as error:
        triage_errors.append(str(error))
    blank_admitted = cov.loc[cov["admitted"], "triage_category"].fillna("").eq("").all()
    chk("every excluded filing has a valid triage_category", not bad_cat and not triage_errors and blank_admitted,
        f"invalid categories: {bad_cat}; incomplete/stale evidence: {len(triage_errors)}")
    admitted_ids = set(adm["adsh"])
    chk("holdings contain admitted filings only", set(hold["adsh"]) <= admitted_ids,
        str(sorted(set(hold["adsh"]) - admitted_ids))[:120])
    # Source row numbers restart in every release. Resolve both parts of the key,
    # and verify filing and period as well as the value on the sampled source rows.
    soi_idx = soi.set_index(["release", "soi_row"])
    periods = sub.set_index("adsh")["period"]
    sampled = hold.sample(min(sample, len(hold)), random_state=7) if len(hold) else hold
    fails = 0
    for row in sampled.itertuples():
        text = str(row.source_rows)
        if not re.fullmatch(r"\d+(;\d+)*", text):
            fails += 1
            continue
        keys = [(row.release, int(value)) for value in text.split(";")]
        ok = all(key in soi_idx.index for key in keys)
        if ok:
            source = soi_idx.loc[keys]
            ok = (source["adsh"].eq(row.adsh).all()
                  and row.period == periods.get(row.adsh)
                  and source["ddate"].eq(row.period).all())
            values = source["fair_value"]
            if pd.notna(row.fair_value):
                # A recovered NUM value requires a separate evidenced validation
                # path before admission; missing source values alone are not proof.
                ok = ok and (values - row.fair_value).abs().le(.5).any()
            else:
                ok = ok and values.isna().all()
        fails += not ok
    chk(f"provenance: sampled rows trace to their SOI rows ({len(sampled)} sampled)",
        fails == 0, f"{fails} failed")
    return res


def main() -> int:
    res = run_checks()
    for name, ok, detail in res:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if not ok and detail else ""))
    n = sum(ok for _, ok, _ in res)
    print(f"{n}/{len(res)} checks pass")
    return 0 if n == len(res) else 1


if __name__ == "__main__":
    sys.exit(main())
