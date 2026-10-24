"""Self-check for Case Study 2B outputs. The grader runs the same checks.

Usage:  python -m lookthrough.check            (from the repository root, with src/ on PYTHONPATH)
"""
import sys

import pandas as pd

from . import load, mapping, paths, reconcile, tables


def run_checks(root=None, sample=25) -> list:
    root = paths.repo_root(root)
    P = paths.load_params(root)
    rdir = paths.release_dir(P, root)
    tol = float(P["reconcile"]["tolerance"])
    sub = load.load_sub(rdir)
    tag = load.load_tag(rdir)
    header = load.soi_header(rdir)
    fv_cols = mapping.map_soi_columns(header, tag).get("fair_value", [])
    soi = load.load_soi(rdir, usecols=["adsh"] + fv_cols)
    num = load.load_num(rdir, tags=[reconcile.FV_TAG])
    filed = reconcile.filed_totals(num, sub).set_index("adsh")["filed_fv"]
    hold = tables.load_table(root / P["outputs"]["panel"] / "holdings")
    cov = pd.read_csv(root / P["outputs"]["reports"] / "coverage.csv", dtype={"adsh": str})
    res = []

    def chk(name, ok, detail=""):
        res.append((name, bool(ok), detail))

    need = ["adsh", "identifier", "fair_value", "source_rows"]
    chk("holdings has the required columns", all(c in hold for c in need), str([c for c in need if c not in hold]))
    need_c = ["adsh", "holdings_fv", "filed_fv", "gap_pct", "admitted"]
    chk("coverage.csv has the required columns", all(c in cov for c in need_c), str([c for c in need_c if c not in cov]))
    if not all(c in hold for c in need) or not all(c in cov for c in need_c):
        return res
    cov["admitted"] = cov["admitted"].astype(str).str.lower().isin(["true", "1"])
    expected = set(soi["adsh"]) & set(sub["adsh"])
    dropped = sorted(expected - set(cov["adsh"]))
    chk("every filing with SOI rows is in coverage.csv (none dropped)", not dropped,
        f"{len(dropped)} missing, e.g. {dropped[:3]}")
    bad = [a for a, v in zip(cov["adsh"], cov["filed_fv"]) if a in filed and abs(filed[a] - v) > 1.0]
    chk("filed totals match NUM", not bad, f"{len(bad)} mismatched")
    sums = hold.groupby("adsh")["fair_value"].sum()
    adm = cov[cov["admitted"]]
    bad = [a for a, v in zip(adm["adsh"], adm["holdings_fv"]) if abs(sums.get(a, 0.0) - v) > 1.0]
    chk("holdings sum to the reported holdings_fv", not bad, f"{len(bad)} mismatched")
    gap_ok = ((cov["holdings_fv"] - cov["filed_fv"]) / cov["filed_fv"] - cov["gap_pct"]).abs().fillna(0).le(1e-6)
    chk("gap_pct is computed correctly", gap_ok.all(), f"{int((~gap_ok).sum())} wrong")
    adm_ok = (cov["gap_pct"].abs().le(tol + 1e-9) == cov["admitted"]) | cov["filed_fv"].isna()
    chk(f"admission follows the tolerance ({tol:.2%})", adm_ok.all(), f"{int((~adm_ok).sum())} inconsistent")
    cats = cov.loc[~cov["admitted"], "triage_category"].fillna("") if "triage_category" in cov else pd.Series(["missing column"])
    bad_cat = sorted(set(cats) - set(reconcile.TRIAGE))
    chk("every excluded filing has a valid triage_category", not bad_cat,
        f"found {bad_cat}; allowed: {', '.join(reconcile.TRIAGE)}")
    chk("holdings contain admitted filings only", set(hold["adsh"]) <= set(adm["adsh"]),
        str(sorted(set(hold["adsh"]) - set(adm["adsh"])))[:120])
    soi_idx = soi.set_index("soi_row")
    s = hold.sample(min(sample, len(hold)), random_state=7) if len(hold) else hold
    fails = 0
    for r in s.itertuples():
        ids = [int(x) for x in str(r.source_rows).split(";") if x.strip().isdigit()]
        ok = bool(ids) and all(i in soi_idx.index and soi_idx.at[i, "adsh"] == r.adsh for i in ids)
        if ok and pd.notna(r.fair_value):
            vals = pd.concat([pd.to_numeric(soi_idx.loc[ids, c], errors="coerce") for c in fv_cols]) \
                if fv_cols else pd.Series(dtype=float)
            ok = (vals - r.fair_value).abs().le(0.5).any() or vals.isna().all()
        fails += not ok
    chk(f"provenance: sampled rows trace to their SOI rows ({len(s)} sampled)", fails == 0, f"{fails} failed")
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
