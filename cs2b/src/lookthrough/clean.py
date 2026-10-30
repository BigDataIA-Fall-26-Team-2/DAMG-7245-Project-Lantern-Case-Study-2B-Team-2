"""Cleaning rules: each returns a mask of rows to DROP and a reason."""
import re

import pandas as pd

# Accept the spaced "Sub Total" spelling. Match Net Assets only as a
# complete label: names such as "Net Assets Capital" are not summaries.
TOTAL = (r"^\s*(?:sub\s*)?total\b|\btotal investments\b"
         r"|^\s*net\s+assets\s*$")
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


# Classification-only labels observed in the schedules. This vocabulary contains
# sectors/countries, never issuers, accession numbers or dollar amounts. Unknown
# words are deliberately not matched; extend it only with reviewed evidence.
SUMMARY_SECTORS = """Aerospace & Defense;Aerospace Defense;Air Freight & Logistics;
Auto Components;Automobiles;Automotive;Banking, Finance, Insurance & Real Estate;
Beverage, Food & Tobacco;Building Products;Capital Equipment;Chemicals;
Chemicals, Plastics, & Rubber;Commercial Services & Supplies;Commercial Services and Supplies;
Construction & Building;Construction & Engineering;Consumer Finance;
Consumer Goods: Durable;Consumer Goods: Non-Durable;Containers, Packaging & Glass;
Distributors;Diversified Financial Services;Diversified Financials;
Diversified Telecommunication Services;Electrical Equipment;Energy: Electricity;
Energy: Oil & Gas;Entertainment;Environmental Industries;Food & Staples Retailing;
Food Products;Forest Products & Paper;Health Care Equipment & Supplies;
Health Care Providers & Services;Healthcare Providers & Services;Health Care Technology;
Healthcare & Pharmaceuticals;High Tech Industries;Hotel, Gaming & Leisure;
Hotels Restaurants Leisure;Hotels, Restaurants & Leisure;Hotels, Household Products;
Household Durables;Household Products;Insurance;Interactive Media & Services;
IT Services;Leisure Products;Life Sciences Tools & Services;Machinery;Media;
Media: Advertising, Printing & Publishing;Media: Broadcasting & Subscription;
Media: Diversified & Production;Metals & Mining;Personal Products;Professional Services;
Real Estate Management & Development;Retail;Road & Rail;Services: Business;Services: Consumer;Software;Specialty Retail;
Telecommunications;Trading Companies & Distributors;Transportation & Logistics;
Transportation Infrastructure;Transportation: Cargo;Transportation: Consumer;
Utilities: Electric;Water Utilities"""
_SECTOR = "(?:" + "|".join(re.escape(x.strip()) for x in SUMMARY_SECTORS.split(";")) + ")"
_COUNTRY = r"(?:Austria|Canada|France|Germany|Ireland|Luxembourg|Netherlands|Puerto Rico|Switzerland|United Kingdom|United States)"
_AFFILIATION = r"(?:(?:non[- ]controlled/)?non[- ]affiliat(?:ed|e)|controlled|affiliated)"
_TYPE = (r"(?:first lien senior secured (?:term )?loans?|preferred equity securities|"
         r"warrants and other equity securit(?:ies|ie)|senior unsecured notes|fund investments)")
_ROOT = (rf"(?:{_AFFILIATION} investments(?:\s*-\s*\d+(?:\.\d+)?% of shareholder's equity)?"
         rf"|(?:portfolio )?investments\s*-\s*{_AFFILIATION})")
# Some extracted category paths repeat a heading or include a page-break label
# (Description, One, Two). They still must consist entirely of known categories.
_COMPONENT = (rf"(?:{_SECTOR}(?: (?:One|Two))?|{_TYPE}|"
              rf"Investments made in (?:the )?{_COUNTRY}|Description|One|Two)")
CATEGORY_SUMMARY = (rf"(?:{_ROOT}(?:\s*-\s*{_COMPONENT})*|"
                    rf"(?:{_SECTOR} )?(?:Investments )?{_TYPE} {_AFFILIATION} Investments)")


def rule_source_disclosures(h: pd.DataFrame):
    """Remove only verified outside-scope cash or uniquely linked source repeats.

    Curated roles/identity links are checked against immutable filing facts by
    evidence.attach. Precision is XBRL decimals, never a fitted gap tolerance.
    Unannotated, conflicted or ambiguous groups remain untouched.
    """
    why = "source-verified cash disclosure or repeated investment fact"
    drop = pd.Series(False, index=h.index)
    required = {"source_role", "source_scope", "source_instrument_key", "source_fact_id",
                "source_decimals", "source_document_sha256", "release", "subsidiary", "n_conflicts"}
    if not required <= set(h):
        return drop, why
    fv = h["fair_value"]
    decimals = pd.to_numeric(h["source_decimals"], errors="coerce")
    verified = (h["source_fact_id"].notna() & h["source_instrument_key"].notna()
                & h["source_document_sha256"].notna() & h["n_conflicts"].eq(0)
                & fv.gt(0) & fv.lt(float("inf")) & decimals.between(-12, 12))
    cash = (verified & h["source_role"].eq("cash_equivalent")
            & h["source_scope"].eq("outside_investment_total"))
    drop |= cash & ~_matches(h, SHORT_TERM_INV)
    # Include invalid members in each group so a conflict cannot disappear and
    # turn an ambiguous three-row group into an apparently unique pair.
    annotated = h[h["source_instrument_key"].notna()]
    keys = ["adsh", "ddate", "release", "subsidiary", "source_instrument_key",
            "source_document_sha256"]
    for _, group in annotated.groupby(keys, dropna=False, sort=False):
        if len(group) != 2 or not verified.loc[group.index].all():
            continue
        primary = group[group["source_role"].eq("schedule")]
        copies = group[group["source_role"].isin(["narrative_repeat", "rollforward_repeat"])]
        if len(primary) != 1 or len(copies) != 1 or not group["source_scope"].eq("investment").all():
            continue
        i, j = primary.index[0], copies.index[0]
        if h.at[i, "source_fact_id"] == h.at[j, "source_fact_id"]:
            continue
        if h.loc[j, ["cost", "principal"]].notna().any():
            continue
        error_bound = .5 * (10. ** -decimals[i] + 10. ** -decimals[j])
        if abs(fv[i] - fv[j]) <= error_bound:
            drop[j] = True
    return drop, why


def rule_totals(h: pd.DataFrame):
    named_total = _matches(h, TOTAL) & ~_matches(h, NOT_A_TOTAL)
    # Full-match a classification path, never a prefix of a borrower name.
    labels = h["identifier"].str.strip().str.replace(r"\s+", " ", regex=True)
    category = labels.str.fullmatch(CATEGORY_SUMMARY, case=False, na=False)
    # A complete portfolio classification label, not an issuer or instrument.
    category |= labels.str.fullmatch(r"co[- ]investments?", case=False, na=False)
    # A sector/type label without affiliation is less conclusive. Require a
    # surviving detailed instrument in the same filing/period with BOTH equal
    # cost and fair value. No rounding or filed-total matching is involved.
    short = labels.str.fullmatch(rf"{_SECTOR} {_TYPE}", case=False, na=False)
    if {"cost", "fair_value"} <= set(h):
        # Classification headings with no amounts are not missing-value
        # investments. The common terms/conflict guards below still apply.
        header = labels.str.fullmatch(rf"(?:{_SECTOR} )?{_TYPE}", case=False, na=False)
        category |= header & h[["cost", "fair_value"]].isna().all(axis=1)
    match_fields = ["adsh", "ddate", "cost", "fair_value"]
    match_fields += [c for c in ("release", "subsidiary") if c in h]
    if set(match_fields + ["maturity"]) <= set(h):
        detail = h[~category & ~short & ~named_total & h["maturity"].notna()]
        detail = detail.dropna(subset=["cost", "fair_value"])
        detail = detail[detail[["cost", "fair_value"]].abs().ne(float("inf")).all(axis=1)]
        if "n_conflicts" in detail:
            detail = detail[detail["n_conflicts"].eq(0)]
        pairs = set(detail[match_fields].fillna("").itertuples(index=False, name=None))
        witnessed = pd.Series(
            [key in pairs for key in h[match_fields].fillna("").itertuples(index=False, name=None)],
            index=h.index)
        category |= short & witnessed
    terms = [c for c in ("principal", "maturity", "interest_rate", "spread", "pik_rate") if c in h]
    if terms:
        category &= ~h[terms].notna().any(axis=1)
    if "n_conflicts" in h:
        category &= h["n_conflicts"].eq(0)
    return (named_total | category,
            "identifier names a total, subtotal or classification-only summary")


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


COMMITMENT_ROW = (r"(?i)\bcommitment type\b.*\bcommitment expiration date\b")


def rule_commitment_rows(h: pd.DataFrame):
    """Drop rows from the unfunded-commitments table. Some filers tag each
    undrawn commitment on the identifier axis ("... Commitment Type Revolver
    Commitment Expiration Date 07/28/2031"), with a fair value of zero or a
    small negative and no cost or principal. They are not holdings: the
    funded part of the same loan is already in the schedule. A row is
    dropped only if its identifier names both the commitment type and the
    expiration date and it carries no cost and no principal."""
    why = "unfunded-commitment table row, not a holding"
    t = h["identifier"].fillna("").astype(str)
    terms = pd.Series(False, index=h.index)
    for c in ("cost", "principal"):
        if c in h:
            terms |= h[c].notna()
    return t.str.contains(COMMITMENT_ROW, regex=True) & ~terms, why


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
    # Remove only reviewed classification prefixes. Unknown wording stays.
    s = re.sub(
        r"^(?:(?:non[- ]controlled[, ]+(?:non[- ]affiliated|affiliated) investments|"
        r"control investments|equity investments|debt investments|"
        r"first lien senior secured|multi-sector holdings)[, ]+)+",
        "", str(identifier).strip(), flags=re.I)
    s = re.split(r"\s+Investment Type\s+", s, flags=re.I)[0]
    s = re.split(r"\s*\|\s*|\s*,\s*", s)[0]
    return re.sub(r"\s+\d+$", "", s).strip().lower()


# Debt forms that name different instruments. A copy and its counterpart
# that both name a form must name the same one ("revolver" never matches
# "term loan"); a row naming none ("Secured Debt 1.1") is compatible.
DEBT_FORMS = [("revolver", r"\brevolv\w*"),
              ("delayed draw", r"\bdelayed[- ]draw\b|\bddtl\b"),
              ("term loan", r"\bterm (?:loan|note|debt)\b"),
              ("note", r"\b(?:notes?|bonds?|debentures?)\b")]


def debt_form(identifier) -> str:
    t = str(identifier or "").lower()
    for name, pat in DEBT_FORMS:
        if re.search(pat, t):
            return name
    return ""


def add_rollforward_evidence(h: pd.DataFrame) -> pd.DataFrame:
    """Add `rf_opening`: True when the same filing, identifier and
    subsidiary also has a comparative-period row with a fair value but no
    cost and no principal. That is the opening balance of the affiliated-
    investments roll-forward table, which reports beginning and ending fair
    value only; schedule rows report cost or principal. Call this on all
    coalesced holdings (current and comparative) before keeping the current
    rows."""
    out = h.copy()
    if out.empty or "is_current" not in out:
        out["rf_opening"] = False
        return out
    sub = (out["subsidiary"] if "subsidiary" in out
           else pd.Series(None, index=out.index)).fillna("")
    key = list(zip(out["adsh"], out["identifier"].astype(str).str.strip(),
                   sub))
    prior = (~out["is_current"] & out["fair_value"].notna()
             & out["cost"].isna() & out["principal"].isna())
    opening = {k for k, p in zip(key, prior) if p}
    out["rf_opening"] = [k in opening for k in key]
    out["rf_opening"] &= out["is_current"]
    return out


def rule_rollforward_copies(h: pd.DataFrame):
    """Drop holdings repeated from the affiliated-investments roll-forward
    table. That table restates each affiliate holding's ending fair value
    beside its opening value and flows, so the holding is counted twice.

    A row is dropped only when all of these hold:
      * it has a positive fair value and no cost or principal;
      * it has roll-forward evidence (`rf_opening`, from
        add_rollforward_evidence): its identifier also carries an opening
        fair value with no cost or principal. Without that column, or without
        the evidence, the row is kept;
      * the same filing and period has a holding of the same issuer, with the
        identical fair value and cost or principal (the schedule line);
      * the two are compatible instruments: debt never matches equity, and
        two debt rows that both name a form must name the same one (a
        revolver is not a copy of a term loan);
      * that schedule line has not already vouched for another copy.
    Ambiguous candidates are kept. Negative values are unfunded
    commitments and are never dropped."""
    why = "affiliate roll-forward copy of a holding already in the schedule"
    drop = pd.Series(False, index=h.index)
    if h.empty or "rf_opening" not in h:
        return drop, why
    fv = h["fair_value"]
    has_terms = h["cost"].notna() | h["principal"].notna()
    bare = (fv.notna() & (fv > 0) & ~has_terms
            & h["rf_opening"].fillna(False).astype(bool))
    full = fv.notna() & has_terms
    if not bare.any() or not full.any():
        return drop, why
    iss = h["identifier"].fillna("").map(_issuer_key)
    kind = h["identifier"].map(instrument_kind)
    form = h["identifier"].map(debt_form)
    # Copies may not borrow evidence from another release or JV portfolio.
    context_cols = ["adsh", "ddate"] + [c for c in ("release", "subsidiary") if c in h]
    contexts = h[context_cols].fillna("")
    context = dict(zip(h.index, contexts.itertuples(index=False, name=None)))
    # First-out/last-out are distinct tranches even when both say delayed draw.
    priority = h["identifier"].fillna("").str.extract(
        r"(?i)\b(first[- ]out|last[- ]out)\b", expand=False).fillna("").str.lower().str.replace(" ", "-")
    twins = {}
    for ix in h.index[full]:
        twins.setdefault((context[ix], iss[ix], round(fv[ix])), []).append((kind[ix], form[ix], priority[ix]))
    for ix in h.index[bare]:
        key = (context[ix], iss[ix], round(fv[ix]))
        pool = twins.get(key, [])
        for n, (k, f, p) in enumerate(pool):
            if (_compatible(kind[ix], k) and _compatible(form[ix], f)
                    and priority[ix] == p):
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
RULES = [rule_source_disclosures, rule_totals, rule_cash, rule_commitment_rows,
         rule_jv_portfolio, rule_issuer_subtotals, rule_rollforward_copies]
