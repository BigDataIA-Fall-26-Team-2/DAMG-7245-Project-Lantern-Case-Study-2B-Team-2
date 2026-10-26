"""Cleaning rules: each returns a mask of rows to DROP and a reason."""
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
