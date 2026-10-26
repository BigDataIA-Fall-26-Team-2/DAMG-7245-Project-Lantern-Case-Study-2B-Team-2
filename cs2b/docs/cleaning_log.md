# Cleaning log (Part 2)

Release: 2026q2 (monthly ZIPs 2026_04, 2026_05, 2026_06), combined with `combine.py`.
Every rule follows the `rule_totals` contract (a drop mask and a one-line artifact description).
`reports/cleaning_log.csv` lists each rule, its artifact, the rows it affects and an example;
`reports/rule_impact.csv` shows every filing's gap with all rules and with each rule left out.
Both are written by `PYTHONPATH=src python tools/rule_impact.py`.
SOI row numbers restart in each monthly file, so an example names its month.

## Coverage after each rule

| Rules applied | Admitted filings (of 177) | Share of filed dollars |
|---|---|---|
| Starter rules (`rule_totals`, `rule_cash`) | 73 | 25.8% |
| + `rule_jv_portfolio` | 78 | 27.9% |
| + filer-aware `rule_cash` | 80 | 28.2% |

## rule_jv_portfolio

**Artifact.** Some BDCs disclose the full portfolio of a joint venture they invest in but do not
consolidate. Those rows carry the `Investment Company, Nonconsolidated Subsidiary Axis`, kept by
`combine.load_soi_all` as `subsidiary` (and made part of the holding key in Part 1). The loans
belong to the JV, not to the BDC: the BDC's filed total counts its stake in the JV, not every
loan inside it, so counting these rows inflates the BDC's holdings.

**Example.** Bain Capital Specialty Finance, adsh 0001193125-26-217068 (2026_05), SOI row 32355:
a first lien senior secured loan to ATS (Aerospace & Defense, fair value $20.06M) listed under
Bain Capital Senior Loan Program, LLC. The filing lists 201 such JV rows across two JVs (Bain
Capital Senior Loan Program, 132 rows; International Senior Loan Program, 69 rows) totalling
$2.31bn, which is exactly its overcount: the gap falls from +93.5% to 0.000%.

**Rows affected.** 1,014 current-period holdings.

**Effect.** 7 filings change; 5 are newly admitted and none gets worse or loses admission:

| Filing | adsh | Gap before | Gap after |
|---|---|---|---|
| Bain Capital Specialty Finance | 0001193125-26-217068 | +93.5% | 0.000% |
| New Mountain Finance | 0001496099-26-000016 | +70.7% | +0.1% |
| Oaktree Specialty Lending | 0001414932-26-000012 | +19.8% | +1.0% |
| New Mountain Private Credit Fund | 0002037804-26-000010 | +16.1% | 0.000% |
| Bain Capital Private Credit | 0001193125-26-224183 | +22.4% | 0.000% |
| AGL Private Credit Income Fund | 0001193125-26-214378 | +20.9% | +2.4% (still excluded) |
| Franklin BSP Capital | 0001825248-26-000017 | +36.8% | +35.1% (still excluded) |

Several filings land at exactly 0.000%, which is strong evidence the artifact is real rather
than a rule fitted to force a match.

**Test.** `test_jv_portfolio_rule_drops_only_jv_rows`: the same loan appears as the BDC's own
holding and again inside a JV; only the JV copy is dropped, and nothing is dropped when there
is no `subsidiary` column.

## rule_totals (starter kit)

To be completed: verify the example in `reports/cleaning_log.csv` in its filing.

## rule_cash (starter kit, made filer-aware)

**Artifact.** Some schedules list cash and money-market lines. Whether the filed total includes
them varies by filer, and the filer's own label says which: a money-market fund presented as a
*short-term investment* is part of the investment portfolio and is in the total; a line presented
as *cash and cash equivalents* is not. The starter rule dropped every such line.

**Change.** `rule_cash` still drops cash and money-market lines, except those whose identifier
labels them a short-term investment (`SHORT_TERM_INV`).

**Examples.**
- Kept: Palmer Square Capital BDC, adsh 0001193125-26-207523 (2026_05), SOI row 143944,
  "Short-Term Investments Fidelity Investments Money Market Government Portfolio", $23.37M.
  Gap −2.02% → 0.000%. Great Elm Capital, adsh 0001193125-26-204228, SOI row 120300,
  "Short-Term Investments Money Market", $9.60M. Gap −3.47% → 0.000%.
- Still dropped: Blackstone Secured Lending, adsh 0001736035-26-000010, SOI row 137249,
  "Other Cash and Cash Equivalents", $305.8M. It reconciles (0.000%) only with its cash lines dropped.

**Rows affected.** 36 current-period lines dropped (was 38; the 2 short-term-investment lines are now kept).

**Effect.** 2 filings newly admitted, none harmed.

**Limitation.** The pattern matches the words "money market" anywhere in an identifier, so a
borrower with those words in its name would be dropped. No such borrower appears in 2026q2
(all 38 matching lines were checked).

**Test.** `test_cash_rule_keeps_money_market_labelled_short_term_investment`.

## rule_totals (starter kit)

To be completed: verify the example in `reports/cleaning_log.csv` in its filing.
