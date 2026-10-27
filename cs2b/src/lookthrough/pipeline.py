"""The baseline pipeline in one call (notebook 08, tests, smoke test)."""
from . import clean, combine, holdings, reconcile


def run_baseline(rdir, tolerance, rules=None) -> dict:
    """Coordinate input loading, holding assembly, cleaning and reconciliation.

    Directory callers retain the starter return contract. Mapping callers receive
    canonical rows in `soi` and a per-release `colmap`; reconciliation and
    diagnostics have the same shape in both modes.
    """
    inputs = combine.load_inputs(rdir, num_tags=[reconcile.FV_TAG], custom_fv=True)
    sub, num = inputs["sub"], inputs["num"]
    canon = holdings.split_periods(inputs["canon"], sub)
    h = holdings.coalesce_holdings(canon)
    if rules is None:
        rules = [clean.rule_totals, clean.rule_cash]
    kept, log = clean.apply_rules(h[h["is_current"]], rules)
    filed = reconcile.filed_totals(num, sub)
    rec = reconcile.reconcile(kept, filed, sub, tolerance,
                              soi_adsh=set(inputs["soi"]["adsh"]))
    diag = reconcile.diagnose(rec, kept, num, canon)
    return {**inputs, "canon": canon, "holdings": h, "kept": kept,
            "log": log, "rec": rec, "diag": diag}
