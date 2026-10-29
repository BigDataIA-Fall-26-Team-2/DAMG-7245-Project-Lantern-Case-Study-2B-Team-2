# Cleaning log (Part 2)

Release: 2026q2 (monthly ZIPs 2026_04, 2026_05, 2026_06), combined with `combine.py`.
Every rule follows the `rule_totals` contract (a drop mask and a one-line artifact description).
`reports/cleaning_log.csv` lists each rule, its artifact, the rows it affects and an example;
`reports/rule_impact.csv` shows every filing's gap with all rules and with each rule left out.
Both are written by `PYTHONPATH=src python tools/rule_impact.py`.
SOI row numbers restart in each monthly file, so an example names its month. A row number is
`soi_row` from `combine.load_soi_all`: the row's position in that month's `soi.tsv` counting
from 0 (pandas index), so the line in the file is the row number + 2 (header and 1-based lines).

## Where the rules run

All rules live in `clean.RULES`, applied in that order. `pipeline.run_baseline`,
`tools/rule_impact.py` (coverage with and without each rule) and `tools/break_rules.py`
(`reports/tests_that_fail.md`) all use that one list, so the pipeline and the evidence cannot
drift apart. Each example in `reports/cleaning_log.csv` names its month file and was opened in
the raw `soi.tsv` to confirm it: `reports/cleaning_log_check.md`
(`PYTHONPATH=src python tools/verify_examples.py`).

## Coverage after each rule

| Rules applied | Admitted filings (of 177) | Share of filed dollars |
|---|---|---|
| Starter rules (`rule_totals`, `rule_cash`) | 73 | 25.8% |
| + `rule_jv_portfolio` | 78 | 27.9% |
| + filer-aware `rule_cash` | 80 | 28.2% |
| + `rule_issuer_subtotals` | 86 | 40.9% |
| + `rule_rollforward_copies` | 90 | 43.4% |
| + `rule_totals` false positives fixed | 90 | 43.5% |
| + review fixes (PR #3: name boundary, instrument match, rules see survivors only) | 90 | 43.5% |
| + second review fix (roll-forward evidence, debt forms) | 90 | 43.5% |
| + `rule_commitment_rows` (from Guna's spot check) | 90 | 43.5% |

The same rules in their final pipeline order (`clean.RULES`), adding one at a time:

| Rules applied (final versions) | Admitted filings (of 177) | Share of filed dollars |
|---|---|---|
| `rule_totals` | 74 | 23.6% |
| + `rule_cash` | 75 | 26.1% |
| + `rule_commitment_rows` | 75 | 26.1% |
| + `rule_jv_portfolio` | 80 | 28.2% |
| + `rule_issuer_subtotals` | 85 | 40.2% |
| + `rule_rollforward_copies` | 90 | 43.5% |

## rule_totals (starter kit, false positives fixed)

**Artifact.** Schedules include total and subtotal lines ("Total Investments at Fair Value",
"Total First Lien Secured Debt", "TOTAL INVESTMENTS - 280.5%"). Counting them adds the same
dollars again. Example: Lord Abbett Private Credit Fund, adsh 0000930413-26-001612, SOI row
163030, "Total Investments at Fair Value", $1,413.0M.

**False positives found.** The starter pattern matches any identifier that starts with
"Total", and four real borrowers do: Total Expert, Inc. (a TriplePoint borrower), Total Access
Elevator, LLC, Total Power Limited and Total Safety Holdings, LLC. It also matched one real
PAI Pharma revolver whose description contains "Total Investments" beside a maturity date.

**Change.** A row is not a total when its identifier carries a company suffix (LLC, Inc., Corp.,
Ltd., Limited, L.P., GmbH, Holdings) or a maturity date (`NOT_A_TOTAL`). True totals carry
neither. Rows dropped: 29 (was 42); the 13 kept rows are real holdings.

**Effect.** TriplePoint Venture Growth (adsh 0001580345-26-000021) goes −2.85% → 0.00% and is
admitted: its Total Expert loan ($22.1M, principal $22.5M) had been dropped. TriplePoint Private
Venture Credit (adsh 0001792509-26-000017) goes +0.41% → +2.36% and is no longer admitted. Its
Total Expert loan ($7.35M, principal $7.5M, SOI row 163022) is also real; the earlier admission
came from wrongly dropping it, which happened to offset a separate ~$9.1M overcount. That
overcount is left for triage rather than hidden. Net admitted filings unchanged at 90;
share of dollars 43.4% → 43.5%.

**Tests.** Starter `test_total_rule_spares_ordinary_names` still passes;
`test_total_rule_spares_companies_named_total` covers the fix.

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

## rule_commitment_rows (from the Part 4 spot check)

**Artifact.** Some filers tag each undrawn commitment from their unfunded-commitments note on the
identifier axis. Guna's spot check found one in the sample: T Series BDC, adsh
0001193125-26-219405 (2026_05), SOI row 97935, "Investments in Non-Controlled, Non-Affiliated
First Lien Debt Cerity Partners, LLC Commitment Type Revolver Commitment Expiration Date
07/28/2031", with no fair value, cost or principal. It is not a holding: the funded part of the
loan is already in the schedule.

**Rule.** Drop a row whose identifier names both a commitment type and a commitment expiration
date ("Commitment Type ... Commitment Expiration Date") and that carries no cost and no
principal. Rows naming only a commitment type (one filer, 77 rows) are kept, because they could
not be confirmed as commitment-table rows.

**Example.** 7Ridge Investments, adsh 0001193125-26-222241 (2026_05), SOI row 87437 (verified in
`reports/cleaning_log_check.md`).

**Rows affected.** 2,357 current-period rows in 11 filings (Antares x3, North Haven x2, Morgan
Stanley Direct Lending, MSD, LGAM, SL Investment Fund II, T Series, Vista). Fair values are zero
or blank, or small negatives (unrealized loss on the undrawn amount); none has cost or
principal.

**Effect.** No filing changes admission (still 90 of 177, 43.5% of dollars). Four admitted
filings move closer to their filed totals because their small negatives were already outside
the filed total: North Haven Private Income Fund A −0.20% → 0.000%, Antares Strategic Credit
Fund II −0.18% → 0.000%, Antares Private Credit Fund −0.19% → −0.001%, Antares Strategic Credit
Fund −0.22% → −0.016%. None moves further away. The panel no longer lists these rows as
holdings, so the Part 4 spot check re-picks its T Series holding.

**Relation to the negative-value investigation below.** That test dropped every negative value
and harmed 4 filings, because many negatives are schedule lines the filer nets into its total.
This rule uses the commitment-table wording, not the sign, so those schedule lines are kept.

**Test.** `test_commitment_rule_drops_only_unfunded_commitment_rows`.

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

## rule_issuer_subtotals

**Artifact.** Some schedules list a company-level line and then each of the company's
instruments underneath it. The company line is the sum of its instruments, so counting both
counts the same dollars twice. These lines do not contain the word "total", so `rule_totals`
does not catch them.

**Rule.** Drop a row when (1) its identifier is the start of other identifiers in the same
filing and period, its children, and (2) its fair value equals the children's sum (within 0.2%,
or $1 for small values). Text after the parent that only numbers a sibling tranche ("One", "2")
or repeats the label ("[Member]") does not make a child. JV portfolio rows are not used as
children. The filed total is not used, so a row is only dropped when the arithmetic shows it
repeats lines already counted.

**Example.** Ares Capital, adsh 0001628280-26-027688 (2026_04), SOI row 1781,
"Ivy Hill Asset Management, L.P.", $2,661.2M, equal to its "Member interest" ($1,899.0M, SOI
row 1777) plus its "Subordinated revolving loan" ($762.2M, SOI row 1779). Ares goes from
+16.59% to +0.11% and is admitted. Prospect Capital: "First Tower Finance Company LLC"
$952.3M = Class A Units $503.0M + First Lien Term Loan $449.3M.

**Rows affected.** 133 current-period rows in 20 filings (382 before the review fixes below).

**Effect.** 27 filings change; 6 newly admitted (Ares Capital, Ares Strategic Income Fund,
Golub Capital BDC, Blue Owl Technology Income, TPG Twin Brook Capital Income Fund, Advanced
Flower Capital); none harmed and none moved further from its filed total. Large overcounts
shrink but remain, for example FS KKR +47.6% → +21.0% and Prospect +61.3% → +4.0%.

**False positives found and fixed.** A first version dropped 5 holdings that were not
subtotals: identical sibling tranches ("... Revolver" and "... Revolver One" at Stellus Private
Credit, Kayne Anderson, Antares), two warrants within the old $1,000 tolerance (Eagle Point),
and a repeated "[Member]" label (Lord Abbett). The sibling-suffix exclusion and the tighter
tolerance remove all five.

**Test.** `test_issuer_subtotal_rule_drops_only_true_subtotals`.

## rule_rollforward_copies

**Artifact.** BDCs must file an affiliated-investments roll-forward table (Rule 12-14) that
restates each affiliate holding's beginning and ending fair value beside its additions,
reductions, gains and income. The SOI data set carries those rows on the same identifier axis,
so each affiliate holding appears twice: once from the schedule (with cost, principal, rate)
and once from the roll-forward (fair value only).

**Rule.** Drop a holding that has a positive fair value but no cost and no principal only when
(1) its identifier also carries a roll-forward opening balance, i.e. a comparative-period fair
value with no cost and no principal (`clean.add_rollforward_evidence` sets `rf_opening`), and
(2) the same filing and period has a holding of the same issuer (identifier text before " | "
or ",", without a trailing tranche number) with the identical fair value that does carry cost
or principal, (3) of a compatible instrument (debt never matches equity; two debt rows that
both name a form must name the same one, so a revolver is never a copy of a term loan), and
(4) that holding has not already vouched for another copy. Anything less is ambiguous and the
row is kept. The filed total is not used.

**Example.** FS KKR Capital, adsh 0001628280-26-033118 (2026_05). Schedule line SOI row 171216,
"Wittur Holding GmbH | Capital Goods 1", fair value $65.9M, cost $63.5M, principal $58.7M.
Roll-forward copy "Wittur Holding GmbH 1": SOI row 171222 repeats the $65.9M ending fair value
with no cost or principal, and row 171223 holds the quarter's roll-forward flows (gross
additions $2.0M, interest income $0.2M); row 171221 holds the prior year's flows. The copy is dropped; the schedule line is kept.

**Rows affected.** 319 current-period rows ($6.77bn) in 20 filings (252 before the first review
fix, 324 after it, 319 after the second; see "Review fixes" below).

**Effect.** 4 newly admitted (Main Street Capital +12.82% → −0.04%, MSC Income Fund
+4.41% → −0.49%, Monroe Capital Income Plus, Lafayette Square); none harmed and none moved
further from its filed total. FS KKR +21.0% → +10.8%, CION +37.6% → +7.3%, Franklin BSP
+35.1% → +16.8%.

**Limitation.** Negative values are left alone. Allowing them brought MSC Income Fund to
exactly 0.00%, so its unfunded commitments also appear to be repeated in the roll-forward, but
it moved HPS Corporate Lending and Crescent Capital BDC slightly further from their totals. The
positive-only version is kept; negative repeated values are left for the unfunded-commitment
investigation.

**Tests.** `test_rollforward_copy_rule_drops_only_bare_twins`,
`test_rollforward_evidence_is_an_opening_value_without_cost_or_principal`, and the review
regression tests below.

## Review fixes (PR #3, Lokesh)

Lokesh reproduced two unintended deletions on small hand-made inputs. Both were real, and both
are fixed with regression tests that fail on the pre-review code (23 of 28 tests pass there)
and pass now (28 of 28).

**P2, `rule_issuer_subtotals`: an unrestricted name prefix.** "ABC" was treated as the parent
of "ABCD LLC" because one string starts with the other, and equal values then "proved" a
subtotal. Now a child counts only if the parent's name ends at a word boundary (the next
character is a space, comma, "|" or bracket), and not if the extra text is only a company
suffix ("XYZ" / "XYZ, LLC") or a tranche number. A parent that itself names an instrument
("Acme, Inc. | First lien loan") is a holding, not an issuer subtotal, so it is kept. Tests:
`test_issuer_subtotal_rule_needs_a_real_name_boundary`,
`test_issuer_subtotal_rule_keeps_a_parent_that_names_an_instrument`.

**P1, `rule_rollforward_copies`: matching by issuer and value only.** A preferred-equity holding
was dropped as a "copy" of a same-value loan of the same issuer. Now each identifier is
classed as debt, equity or unknown from its words (`clean.instrument_kind`); a copy matches only
a compatible counterpart (debt never matches equity), and each counterpart vouches for one copy.
The `affiliation` column, which would show roll-forward provenance directly, is empty for every
holding in 2026q2, so the evidence used is: no cost and no principal, identical value, same
issuer, compatible instrument, one-to-one. Tests:
`test_rollforward_rule_keeps_a_distinct_instrument_with_the_same_value`,
`test_rollforward_rule_lets_one_holding_vouch_for_one_copy`.

**P1, rule interaction in `apply_rules`.** Every rule was given the original frame, so a JV loan
already dropped by `rule_jv_portfolio` could still serve as the counterpart for the BDC's own
holding, deleting both. `apply_rules` now gives each rule only the rows the earlier rules kept.
Test: `test_rollforward_rule_ignores_a_counterpart_already_dropped_as_jv`.

**Effect on 2026q2.** The fixed rules drop no new rows and keep 177 rows ($912.5M, 20 filings)
that the earlier versions dropped. Admitted filings stay at 90 of 177 and 43.5% of dollars; no
admitted filing is lost, and MSC Income (−0.49% → 0.00%) and Main Street (−0.04% → 0.00%) move
closer. Seven filings that were not admitted move further from their totals because candidates
that name an instrument are now kept rather than guessed: Rand Capital (+9.1% → +33.4%),
Investcorp Credit Management (+7.5% → +15.1%), Remora Capital (+200% → +300%), Steele Creek
(+211% → +300%), Prospect Capital (+2.7% → +3.3%), Gladstone Investment (+6.1% → +6.5%) and CION
(+7.2% → +7.8%). They are passed to triage: their extra lines are instrument-level subtotals the
data does not mark as such. Ares Capital (+0.08% → +0.38%) and Stellus (+0.19% → +0.48%) stay
admitted. The cited examples are unchanged: Ivy Hill (SOI row 1781) is still dropped as a
subtotal and Wittur's schedule line (SOI row 171216) is still kept with its copy dropped.


### Second review (commit 6fd1844)

Lokesh showed the debt/equity check was still too coarse: with "Acme | First lien term loan"
($100, with cost and principal) and "Acme | Revolving credit facility" ($100, without), the
rule deleted the revolver because both are debt. Equal value and the same issuer do not prove
a copy. Two changes:

- **Roll-forward evidence is now required.** A candidate copy must also carry the
  roll-forward's opening balance: a comparative-period fair value with no cost and no
  principal on the same identifier. Schedule lines carry cost or principal in both periods;
  roll-forward lines report beginning and ending value only. Example: Main Street, adsh
  0001396440-26-000073 (2026_05), "AAC Holdings, Inc. | Secured Debt 1.1": SOI row 34572 is the
  opening value ($895K, 2025-12-31), row 34573 the ending value ($940K), neither with cost or
  principal. Of the 324 rows the 6fd1844 rule dropped, 318 have this evidence. Without the
  evidence (or without the `rf_opening` column) a bare row is kept.
- **Debt forms must agree when both are named** (`clean.debt_form`: revolver, delayed draw,
  term loan, note). A row that names no form ("Secured Debt 1.1") stays compatible, because
  schedules and roll-forwards often describe the same loan differently (Adapt Laser's
  roll-forward "Revolving Loan" is the schedule's "Senior Secured First Lien Debt | Maturity 2").

Tests: `test_rollforward_rule_keeps_a_revolver_that_matches_a_term_loan_by_value` (Lokesh's
example, with and without evidence and without the column) and
`test_rollforward_evidence_is_an_opening_value_without_cost_or_principal`; both fail on
6fd1844 and pass now (30 of 30).

**Effect on 2026q2.** Only Prospect Capital changes. Six of its bare term-loan rows have no
opening balance (e.g. "Aventiv Technologies, LLC, Third Out Super Priority First Lien Term
Loan", 2026_05 SOI row 41304, $22.7M) and are now kept; one evidenced copy, "Victor Technology,
LLC" (SOI rows 168821-168822), now takes the counterpart its sibling used to take. Prospect goes
+3.3% → +4.4% and was not admitted either way. Still 90 of 177 filings and 43.5% of dollars; no
admitted filing changes. Wittur's copies (SOI rows 171222, 171227, 171234) are still dropped.
362 evidenced bare rows have no same-value schedule twin and are kept.

## Investigated, no rule: unfunded commitments (negative values)

**What we found.** 7,166 current-period holdings in 107 filings carry a negative fair value,
totalling −$494.9M (about 0.09% of the $542.2bn attempted). 4,225 of them are named as
revolvers, delayed-draw loans or unfunded commitments: the negative value is the unrealized
loss on the undrawn part of a commitment.

**Why no rule.** BDCs net these into the investment total they file. Manulife Private Credit
Fund (adsh 0001193125-26-219274) reconciles at 0.00% with its line "Short-term investments 9.6%
| Less unfunded loan commitments (61.8%)" (−$102.9M) included. Dropping every negative value
was tested: 4 admitted filings would fail (Manulife, Oaktree Specialty Lending, Golub Capital
BDC, Blue Owl Technology Income) and only 2 would gain. Negative values are therefore kept.

**Related observation.** Muzinich BDC lists "Liabilities in Excess of Other Assets" (−$76.3M) on
the identifier axis. It is a net-assets reconciliation line, not a holding; the filing has no
filed total, so it does not affect admission and is left for the triage report.


## Known limitation (from the Part 4 spot check): principal has no currency

`principal` is reported in the loan's own currency while `fair_value` is in USD, and the data set
has no currency column for principal. Guna found Apollo's SPARKLE BIDCO loan (GBP) and a
Blackstone Spectrum loan (EUR). Reconciliation uses fair value only, so coverage is unaffected,
but any price derived as fair value / principal is wrong for non-USD loans. No cleaning rule:
the currency is not in the SOI data, so it is documented in `reports/dependency_check.md`.

## Investigated, no rule: holdings without an identifier (custom axes)

**Rows with a value but no identifier are category totals, not holdings.** 17,278
current-period rows carry a fair value but no `Investment, Identifier Axis` member; together
they come to $5.9 trillion, eleven times the $542.2bn attempted. They are totals by industry,
investment type, affiliation or joint venture, or for the whole filing (for example Ares
Capital, SOI row 1 (2026_04), $11.9bn on the Nonconsolidated Subsidiary Axis for Ivy Hill
with no identifier). `holdings.coalesce` builds holdings only from identified rows, so these
are already excluded, which is correct.

**Five filings have a filed total but no identified holdings.**

| Filing | adsh | What the data set holds | Can it be recovered? |
|---|---|---|---|
| Partners Group Lending Fund | 0001398344-26-009326 | 784 rows on a filer-defined `InvestmentsIdentifier` axis; values under "Investments, Fair Value Disclosure" | No. The custom member is a category ("Investments-non-controlled/non-affiliated [Member]"), not an issuer; summing it gives +615.6% |
| SuRo Capital | 0001493152-26-021430 | Holdings named on `Legal Entity Axis` / `Consolidated Entities Axis` (174 rows) | Not safely. Summing the 84 current rows with a legal-entity name gives +59.5%: they mix holdings with totals on other axes |
| Horizon Technology Finance | 0001437749-26-014916 | No SOI rows in any 2026q2 monthly file (filed total $695.7M) | No: absent from the data set |
| Firsthand Technology Value Fund | 0001437749-26-017006 | No SOI rows in any monthly file | No: absent from the data set |
| Equus Total Return | 0001096906-26-000571 | 18 rows, all filing-level summaries on non-investment axes | No: no holding-level rows |

**Why no rule.** Turning a custom axis into an identifier would need a separate mapping per
filer and, for both filers that use one, still would not reconcile; the result would be
fitted rather than evidenced. These filings stay attempted and unadmitted, and are passed to
triage as three categories: *holdings on a custom axis* (Partners Group, SuRo), *no SOI rows in
the data set* (Horizon, Firsthand), *summary rows only* (Equus).

## Investigated (stretch): fair values under custom or alternative tags

**Question.** Do holdings that lack `InvestmentOwnedAtFairValue` carry their value under a
filer-defined (custom) tag in NUM, or under another standard tag in the SOI, so that it can be
recovered and close an undercount? After cleaning, 17 filings undercount by more than 1%.

**Custom tags in NUM.** Current-period instant facts on the identifier axis with a custom tag
(`version` = the filing's adsh): 3,488 facts in 39 filings. 2,895 of them are commitment or
financial-support amounts (`InvestmentCompanyFinancialCommitmentToInvestee...`,
`UnfundedCommitmentFairValue`), not holding values, and 33 are cash or money-market lines.
Three tags do name a holding's fair value: `InvestmentOwnedFairValueNetOfUnamortizedFees`
(Blue Owl Credit Income, Blue Owl Capital Corp II), `InvestmentOwnedFairValueEndingBalance`
(TCW Direct Lending VII, two filings) and `InvestmentOwnedFairValueBalance` (Goldman Sachs BDC).

- Matched to holdings with no fair value: 34 holdings, $1,111.1M, all at TCW Direct Lending VII.
  They are "Controlled Affiliated Investments ..." ending balances from the affiliate
  roll-forward, so they repeat holdings already counted: recovering them moves adsh
  0001193125-26-141887 from +16.72% to +112.46% and adsh 0001193125-26-221880 from +16.62% to
  +91.68%.
- Goldman Sachs BDC (adsh 0001193125-26-212431, −6.11%): its 9 facts ($143.9M) are affiliate
  roll-forward balances on names that differ from the schedule's ("Non-Controlled Affiliates
  Elah Holdings Inc."); they do not match its missing holdings and do not explain its $197.3M gap.
- Blue Owl's `...NetOfUnamortizedFees` facts sum to −$101.4M and −$1.6M: fee adjustments on
  holdings that already have a fair value, not missing values.

**Alternative standard tag in the SOI.** Lord Abbett Private Credit Fund S (adsh
0000930413-26-001613, −5.66%, $381.5M filed vs $359.9M) reports its joint-venture investment
under the `Investments` tag, not `InvestmentOwnedAtFairValue`: SOI row 17151 (2026_05),
"Investments in Joint Venture [Member]", $21.608M, exactly its shortfall. But the same
fallback also picks up "Second Lien - Secured Debt [Member]" (SOI row 21666, $7.661M), a
category subtotal, and the filing moves to +2.01%. The `Investments` tag appears on current
identified rows of this one filing only.

**Recovering before cleaning does not help either.** If the 34 TCW values are filled in before the
rules run, `rule_rollforward_copies` removes only 1 of them, because the schedule has no holding
with the identical value; TCW still moves from +16.72% to +112.46%.

**Conclusion: no recovery rule.** In 2026q2 the custom fair-value tags carry commitments, fee
adjustments or roll-forward repeats, so recovering them double counts; the alternative-tag
fallback is evidenced for one row of one filing and would be fitted rather than general. The
undercounts are left for triage. Lord Abbett S is recorded as a single named exception
(joint-venture value under `Investments`), and the tag test is kept in
`test_lean_num_keeps_custom_fair_value_facts`.

## Handled upstream: comparative-period rows

Each filing's schedule also carries the prior period's holdings for comparison.
`holdings.split_periods` keeps only rows dated at the filing's own period, so comparative rows
never reach the cleaning rules: across the quarter 94,670 of 191,043 SOI rows (49.6%) are
comparative and are set aside (`reports/period_split.csv`). No cleaning rule is needed.

## Kept on purpose, flagged: equity and warrants

Equity, preferred units and warrants are real holdings and count in the filed total, so no rule
drops them. Instead the pipeline flags them: `clean.flag_debt` adds `is_debt` (from
`clean.is_debt`: a principal or spread, or debt words in the identifier or type), and
`pipeline.run_baseline` applies it to the cleaned holdings. On 2026q2, 7,858 of 63,049 cleaned
holdings are flagged `is_debt = False`, worth $51.7bn (8.9% of cleaned fair value), for example
"Moffitt Holdings, LLC | Preferred Equity" and "Avison Young (Canada) Inc., Class F Common
Shares | Equity". Example of the effect on admission: Main Street Capital (adsh
0001396440-26-000073) keeps 185 equity holdings worth $1,251M, such as "OMi Topco, LLC |
Preferred Member Units" ($79.0M, SOI row 136276), and reconciles at −0.04%. Test:
`test_debt_flag_marks_equity_and_warrants_without_dropping_them`.
