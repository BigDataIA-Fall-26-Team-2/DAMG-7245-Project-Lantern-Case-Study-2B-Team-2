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


# A real holding can start with "Total": companies named "Total Expert,
# Inc." or "Total Access Elevator, LLC", or a loan described with a maturity
# date. Totals never carry a company suffix or a maturity date.
NOT_A_TOTAL = (r"\b(?:llc|inc|corp|ltd|limited|l\.?p|gmbh|holdings)\b\.?"
               r"|maturity date")


def rule_totals(h: pd.DataFrame):
    return (_matches(h, TOTAL) & ~_matches(h, NOT_A_TOTAL),
            "identifier names a total or subtotal")


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


# Words that say what kind of instrument a holding is. Used to stop two
# different instruments of one issuer from being treated as copies or as
# parent and child.
DEBT_WORDS = (r"\b(?:loan|debt|lien|revolv\w*|term|notes?|bonds?|delayed draw|"
              r"senior secured|subordinated|mezzanine|credit facility|ddtl|tranche)\b")
EQUITY_WORDS = (r"\b(?:equity|stock|shares?|units?|preferred|warrants?|common|"
                r"membership|member interest|llc interest|partnership interest|"
                r"lp interest|class [a-z]\b)")
COMPANY_SUFFIX = (r"\s*,?\s*(?:llc|l\.?l\.?c\.?|inc\.?|incorporated|corp\.?|"
                  r"corporation|ltd\.?|limited|l\.?p\.?|lp|gmbh|plc|co\.?|"
                  r"holdings?)\s*\.?\s*")


def instrument_kind(identifier) -> str:
    """'debt', 'equity' or '' (unknown) from an identifier's words."""
    t = str(identifier or "").lower()
    d = re.search(DEBT_WORDS, t) is not None
    e = re.search(EQUITY_WORDS, t) is not None
    return "debt" if d and not e else "equity" if e and not d else ""


def _compatible(a: str, b: str) -> bool:
    return a == b or a == "" or b == ""


# Text after a parent identifier that only numbers a sibling tranche
# ("... Revolver One", "... Warrant 2") or repeats the label ("[Member]"):
# such rows are separate holdings, not parts of the parent.
SIBLING_SUFFIX = (r"\s*(?:one|two|three|four|five|six|seven|eight|nine|ten"
                  r"|\d+|[a-z]|\[member\])\s*")


def rule_issuer_subtotals(h: pd.DataFrame, rel_tol: float = 0.002,
                          abs_tol: float = 1.0):
    """Drop issuer-level subtotal rows: a row whose identifier is the start,
    up to a word boundary, of other identifiers in the same filing and
    period (its children, e.g.
    "Ivy Hill Asset Management, L.P." and "Ivy Hill Asset Management, L.P.,
    Member interest") and whose fair value equals the children's sum. The
    sum check means a real holding is only dropped when the arithmetic shows
    it repeats lines already counted; the filed total is not used. A parent
    that itself names an instrument, a child that differs only by a company
    suffix, and an unrelated name sharing letters ("ABC" / "ABCD LLC") are
    all kept: ambiguous candidates stay in the panel."""
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
                # The parent must end at a word boundary ("ABC" is not the
                # start of "ABCD LLC"), and text that is only a tranche number
                # or a company suffix ("ABC, LLC") names a different holding.
                if (rest and not rest[0].isalnum()
                        and not re.fullmatch(SIBLING_SUFFIX, rest, re.I)
                        and not re.fullmatch(COMPANY_SUFFIX, rest, re.I)):
                    total += fvs[j]
                    n_kids += 1
                j += 1
            # A parent that names a specific instrument ("Acme | First lien
            # loan") is itself a holding, not an issuer subtotal.
            if n_kids == 0 or instrument_kind(parent):
                continue
            if abs(fvs[i] - total) <= max(abs_tol, rel_tol * abs(fvs[i])):
                drop[idx[i]] = True
    return drop, "issuer-level subtotal equal to the sum of its holdings"


def _issuer_key(identifier: str) -> str:
    """Issuer part of an identifier: text before ' | ' or ',' and without a
    trailing tranche number ("Wittur Holding GmbH | Capital Goods 1" and
    "Wittur Holding GmbH 1" both give "wittur holding gmbh")."""
    s = re.split(r"\s*\|\s*|\s*,\s*", str(identifier).strip())[0]
    return re.sub(r"\s+\d+$", "", s).strip().lower()


def rule_rollforward_copies(h: pd.DataFrame):
    """Drop holdings repeated from the affiliated-investments roll-forward
    table. That table restates each affiliate holding's ending fair value
    beside its additions, reductions and income, so the holding is counted
    twice. The copy carries a fair value but no cost and no principal; it is
    dropped only when the same filing and period has a holding of the same
    issuer, with the identical fair value and a compatible instrument (debt
    never matches equity), that does carry cost or principal. Each such
    holding vouches for one copy only. Positive values only: negative values
    are unfunded commitments."""
    why = "affiliate roll-forward copy of a holding already in the schedule"
    drop = pd.Series(False, index=h.index)
    if h.empty:
        return drop, why
    fv = h["fair_value"]
    has_terms = h["cost"].notna() | h["principal"].notna()
    bare = fv.notna() & (fv > 0) & ~has_terms
    full = fv.notna() & has_terms
    if not bare.any() or not full.any():
        return drop, why
    iss = h["identifier"].fillna("").map(_issuer_key)
    kind = h["identifier"].map(instrument_kind)
    twins = {}
    for ix in h.index[full]:
        twins.setdefault((h.at[ix, "adsh"], h.at[ix, "ddate"], iss[ix],
                          round(fv[ix])), []).append(kind[ix])
    for ix in h.index[bare]:
        key = (h.at[ix, "adsh"], h.at[ix, "ddate"], iss[ix], round(fv[ix]))
        pool = twins.get(key, [])
        for n, k in enumerate(pool):
            if _compatible(kind[ix], k):
                drop[ix] = True
                del pool[n]          # one counterpart per copy
                break
    return drop, why


def apply_rules(h: pd.DataFrame, rules) -> tuple:
    """Apply rules in order; return kept rows and a cleaning log. Each rule
    is given only the rows the earlier rules kept.

    The example names the month file when the frame has a `release` column,
    because SOI row numbers restart in each monthly file."""
    log, keep = [], pd.Series(True, index=h.index)
    for rule in rules:
        # A rule sees only rows that survived the earlier rules, so a row
        # already dropped (e.g. a JV loan) cannot serve as evidence for
        # dropping another.
        drop, why = rule(h[keep])
        drop = drop.reindex(h.index, fill_value=False) & keep
        ex = h[drop].head(1)
        if len(ex):
            row = str(ex["source_rows"].iloc[0]).split(";")[0]
            month = (f"{ex['release'].iloc[0]} " if "release" in ex else "")
            example = f"{ex['adsh'].iloc[0]} / {month}soi_row {row}"
        else:
            example = ""
        log.append({"rule": rule.__name__, "artifact": why,
                    "rows_affected": int(drop.sum()),
                    "example": example})
        keep &= ~drop
    return h[keep].copy(), pd.DataFrame(log)


def flag_debt(h: pd.DataFrame) -> pd.DataFrame:
    """Add `is_debt`. Equity, preferred units and warrants are real holdings
    and stay in the panel; they are flagged False, never dropped."""
    out = h.copy()
    out["is_debt"] = is_debt(out)
    return out


def is_debt(h: pd.DataFrame) -> pd.Series:
    text = (h["identifier"].fillna("") + " "
            + h["investment_type"].fillna(""))
    return (h["principal"].notna() | h["spread"].notna()
            | text.str.contains(DEBT, case=False))


# The rules the pipeline applies, in order. tools/rule_impact.py,
# tools/break_rules.py and pipeline.run_baseline all use this one list.
RULES = [rule_totals, rule_cash, rule_jv_portfolio, rule_issuer_subtotals,
         rule_rollforward_copies]
