"""Cleaning rules: each returns a mask of rows to DROP and a reason."""
import re

import pandas as pd

TOTAL = r"^\s*(?:sub)?total\b|\btotal investments\b"
CASH = r"cash and cash equivalents|money market"
DEBT = (r"loan|lien|unitranche|note|bond|revolv|delayed draw"
        r"|subordinat|debt")


def _matches(h, pattern):
    return h["identifier"].str.contains(
        pattern, case=False, regex=True, na=False)


def rule_totals(h: pd.DataFrame):
    return _matches(h, TOTAL), "identifier names a total or subtotal"


# A money-market fund the filer itself lists as a short-term investment is
# part of its investment portfolio (and of its filed total), so it is kept.
SHORT_TERM_INV = r"short[- ]term investment"


def rule_cash(h: pd.DataFrame):
    """Drop cash and money-market lines, except those the filer labels as
    short-term investments: whether the filed total includes them varies by
    filer, and the filer's own label says which (e.g. Palmer Square, Great
    Elm keep them in the total; Blackstone Secured Lending does not)."""
    return (_matches(h, CASH) & ~_matches(h, SHORT_TERM_INV),
            "cash or money-market line (not labelled a short-term investment)")


def rule_jv_portfolio(h: pd.DataFrame):
    """Rows tagged with a `subsidiary` (the Investment Company,
    Nonconsolidated Subsidiary Axis) list the portfolio of an
    unconsolidated joint venture. The BDC's filed total counts its stake
    in the JV, not each loan inside it, so these rows are dropped."""
    if "subsidiary" not in h:
        return pd.Series(False, index=h.index), "no subsidiary column"
    return (h["subsidiary"].notna(),
            "holding of an unconsolidated JV's portfolio, not the BDC's own")


# Text after a parent identifier that only numbers a sibling tranche
# ("... Revolver One", "... Warrant 2") or repeats the label ("[Member]"):
# such rows are separate holdings, not parts of the parent.
SIBLING_SUFFIX = (r"\s*(?:one|two|three|four|five|six|seven|eight|nine|ten"
                  r"|\d+|[a-z]|\[member\])\s*")


def rule_issuer_subtotals(h: pd.DataFrame, rel_tol: float = 0.002,
                          abs_tol: float = 1.0):
    """Drop issuer-level subtotal rows: a row whose identifier is the start
    of other identifiers in the same filing and period (its children, e.g.
    "Ivy Hill Asset Management, L.P." and "Ivy Hill Asset Management, L.P.,
    Member interest") and whose fair value equals the children's sum. The
    sum check means a real holding is only dropped when the arithmetic shows
    it repeats lines already counted; the filed total is not used."""
    drop = pd.Series(False, index=h.index)
    if h.empty:
        return drop, "issuer-level subtotal equal to the sum of its holdings"
    jv = h["subsidiary"].notna() if "subsidiary" in h else drop
    cand = h[h["identifier"].notna() & h["fair_value"].notna() & ~jv]
    for _, g in cand.groupby(["adsh", "ddate"], sort=False):
        g = g.assign(_id=g["identifier"].str.strip()).sort_values("_id")
        ids, fvs, idx = g["_id"].tolist(), g["fair_value"].tolist(), g.index
        for i, parent in enumerate(ids):
            total, j = 0.0, i + 1
            n_kids = 0
            while j < len(ids) and ids[j].startswith(parent):
                rest = ids[j][len(parent):]
                if rest and not re.fullmatch(SIBLING_SUFFIX, rest, re.I):
                    total += fvs[j]
                    n_kids += 1
                j += 1
            if n_kids == 0:
                continue
            if abs(fvs[i] - total) <= max(abs_tol, rel_tol * abs(fvs[i])):
                drop[idx[i]] = True
    return drop, "issuer-level subtotal equal to the sum of its holdings"


def apply_rules(h: pd.DataFrame, rules) -> tuple:
    """Apply rules in order; return kept rows and a cleaning log."""
    log, keep = [], pd.Series(True, index=h.index)
    for rule in rules:
        drop, why = rule(h)
        drop = drop & keep
        ex = h[drop].head(1)
        example = (f"{ex['adsh'].iloc[0]} / soi_row "
                   f"{ex['source_rows'].iloc[0]}" if len(ex) else "")
        log.append({"rule": rule.__name__, "artifact": why,
                    "rows_affected": int(drop.sum()),
                    "example": example})
        keep &= ~drop
    return h[keep].copy(), pd.DataFrame(log)


def is_debt(h: pd.DataFrame) -> pd.Series:
    text = (h["identifier"].fillna("") + " "
            + h["investment_type"].fillna(""))
    return (h["principal"].notna() | h["spread"].notna()
            | text.str.contains(DEBT, case=False))
