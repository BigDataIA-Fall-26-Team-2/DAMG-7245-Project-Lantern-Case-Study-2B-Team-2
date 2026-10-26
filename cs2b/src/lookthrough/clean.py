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


def rule_cash(h: pd.DataFrame):
    return _matches(h, CASH), "cash or money-market line in schedule"


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
