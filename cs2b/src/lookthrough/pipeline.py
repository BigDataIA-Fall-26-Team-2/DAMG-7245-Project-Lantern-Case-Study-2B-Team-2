"""The baseline pipeline in one call (notebook 08, tests, smoke test)."""
from . import clean, holdings, load, mapping, reconcile


def run_baseline(rdir, tolerance, rules=None) -> dict:
    sub, tag = load.load_sub(rdir), load.load_tag(rdir)
    header = load.soi_header(rdir)
    colmap = mapping.map_soi_columns(header, tag)
    soi = load.load_soi(rdir, mapping.soi_usecols(header, colmap))
    soi = soi[soi["adsh"].isin(sub["adsh"])]
    num = load.load_num(rdir, tags=[reconcile.FV_TAG], custom_fv=True)
    canon = holdings.split_periods(mapping.to_canonical(soi, colmap),
                                   sub)
    h = holdings.coalesce_holdings(canon)
    if rules is None:
        rules = [clean.rule_totals, clean.rule_cash]
    kept, log = clean.apply_rules(h[h["is_current"]], rules)
    filed = reconcile.filed_totals(num, sub)
    rec = reconcile.reconcile(kept, filed, sub, tolerance,
                              soi_adsh=set(soi["adsh"]))
    diag = reconcile.diagnose(rec, kept, num, canon)
    return {"sub": sub, "tag": tag, "colmap": colmap, "soi": soi,
            "num": num, "canon": canon, "holdings": h, "kept": kept,
            "log": log, "rec": rec, "diag": diag}
