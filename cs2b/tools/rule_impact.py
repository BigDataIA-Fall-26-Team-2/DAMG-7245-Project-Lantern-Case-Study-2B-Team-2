"""Measure what each cleaning rule changes on the real quarter (2026q2).

Runs the combined months (combine.py) through coalescing, the rules and
reconciliation twice for every rule: with all rules, and with that one rule
left out. Prints admitted filings and dollar coverage, and writes
reports/rule_impact.csv (per filing, gap with and without each rule) and
reports/cleaning_log.csv (rule, artifact, rows affected, example).

    PYTHONPATH=src python tools/rule_impact.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import clean, combine, holdings, paths, pipeline, reconcile  # noqa: E402

RULES = clean.RULES


def prepare(P):
    dirs = combine.release_dirs(P, ROOT)
    inputs = combine.load_inputs(dirs, num_tags=[reconcile.FV_TAG], custom_fv=True)
    sub, can, num = inputs["sub"], inputs["canon"], inputs["num"]
    h = clean.add_rollforward_evidence(
        holdings.coalesce_holdings(holdings.split_periods(can, sub)))
    return sub, can, num, h[h["is_current"]]


def run(cur, sub, num, soi_adsh, rules, tol):
    kept, log = clean.apply_rules(cur, rules)
    rec = reconcile.reconcile(kept, reconcile.filed_totals(num, sub), sub,
                              tol, soi_adsh=soi_adsh)
    return rec, log


def summary(rec):
    coverage = reconcile.coverage(rec)
    return (coverage["filings_admitted"], coverage["filings_attempted"],
            coverage["share_of_dollars"])


if __name__ == "__main__":
    P = paths.load_params(ROOT)
    RULES = pipeline.configured_rules(P)
    tol = P["reconcile"]["tolerance"]
    sub, can, num, cur = prepare(P)
    ids = set(can["adsh"])
    base, log = run(cur, sub, num, ids, RULES, tol)
    a, n, d = summary(base)
    print(f"ALL RULES: admitted {a} of {n} filings, {d:.1%} of filed dollars")
    print(log.to_string(index=False))
    out = base[["adsh", "name", "filed_fv", "gap_pct", "admitted"]].copy()
    for r in RULES:
        rec, _ = run(cur, sub, num, ids, [x for x in RULES if x is not r], tol)
        a2, _, d2 = summary(rec)
        print(f"without {r.__name__:22s} admitted {a2:3d}, {d2:.1%} of dollars")
        m = rec.set_index("adsh")
        out[f"gap_without_{r.__name__}"] = out["adsh"].map(m["gap_pct"])
        out[f"admitted_without_{r.__name__}"] = out["adsh"].map(m["admitted"])
    (ROOT / "reports").mkdir(exist_ok=True)
    log.to_csv(ROOT / "reports" / "cleaning_log.csv", index=False)
    out.to_csv(ROOT / "reports" / "rule_impact.csv", index=False)
    print("wrote reports/rule_impact.csv and reports/cleaning_log.csv")
