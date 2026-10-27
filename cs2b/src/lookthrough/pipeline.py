"""The baseline pipeline in one call (notebook 08, tests, smoke test)."""
from . import clean, combine, holdings, reconcile


def configured_rules(params: dict) -> list:
    """Resolve an ordered list of named cleaning rules, without silent fallback.

    Names must refer to rule_* functions exported by clean.py. This lets Part 2
    supply implementations without duplicating their logic in the orchestrator.
    """
    names = params.get("cleaning", {}).get("rules", ["rule_totals", "rule_cash"])
    if not isinstance(names, list) or not names or any(not isinstance(n, str) for n in names):
        raise ValueError("cleaning.rules must be a non-empty list of rule names")
    if len(set(names)) != len(names):
        raise ValueError("cleaning.rules must not contain duplicates")
    rules = []
    for name in names:
        rule = getattr(clean, name, None)
        if not name.startswith("rule_") or not callable(rule):
            raise ValueError(f"Cleaning rule {name!r} is unavailable; integrate its reviewed implementation first")
        rules.append(rule)
    return rules


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
