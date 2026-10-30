# Canonical holdings schema

Release: 2026q2 = monthly SEC BDC ZIPs 2026_04, 2026_05, 2026_06 (2026_06 has no filings).
Mapping is by XBRL tag via `mapping.map_soi_columns`, using labels from the TAG tables of all three months (`combine.load_tag_all`), never by column position.

| Field | Source tag or axis | SOI column(s) in our release | Type | Notes |
|---|---|---|---|---|
| fair_value | InvestmentOwnedAtFairValue | `Investment Owned, Fair Value`; `Initial fair value of Investment` | float, USD | The us-gaap/2026 version of this tag carries the label "Initial fair value of Investment", and nearly all values sit in that column (May: 150,672 rows; April: 4,177 of 4,378); no row fills both. April's own TAG table lists only the older label, so per-month mapping found 0 April fair values. Fixed in `combine.load_tag_all`, which merges all months' TAG tables before mapping. |
| cost | InvestmentOwnedAtCost | `Investment Owned, Cost`; `Adjusted cost basis` | float, USD | Same label issue as fair_value (us-gaap/2026 label "Adjusted cost basis"); same fix. |
| principal | InvestmentOwnedBalancePrincipalAmount | `Investment Owned, Balance, Principal Amount` | float, USD | Filled on 52% of May rows. Stored without a currency: non-dollar principal (for example £ or €) appears as a plain number (see `reports/dependency_check.md`). `Investment Owned, Face Amount` is not used as a fallback (see below). |
| interest_rate | InvestmentInterestRate | `Investment Interest Rate` | float, decimal | Median 0.087 (8.7%). Max 8.0, so some filers may report in percent units. Flag for cleaning. |
| spread | InvestmentBasisSpreadVariableRate | `Investment, Basis Spread, Variable Rate` | float, decimal | Median 0.05. Max 10.0, same units concern. |
| maturity | InvestmentMaturityDate | `Investment Maturity Date` | date | Already ISO (YYYY-MM-DD) in May; normalized by `load.norm_date`. |
| pik_rate | InvestmentInterestRatePaidInKind | `Investment, Interest Rate, Paid in Kind` | float, decimal | Filled on 6% of May rows. Max 7.5, units concern. |
| pct_net_assets | InvestmentOwnedPercentOfNetAssets | `Investment Owned, Net Assets, Percentage` | float, decimal | Median 0.002. Max 295.2, likely percent units or a total row. Flag for cleaning. |
| identifier | Investment, Identifier Axis | `Investment, Identifier Axis` | text | Filled on 76% of May rows; missing ones are candidates for totals or custom axes. Free text, format varies by filer. |
| investment_type | Investment Type Axis | `Investment Type Axis` | text | Filled on 9% of May rows. |
| industry | Industry Sector Axis | `Industry Sector Axis` | text | Filled on 11% of May rows. |
| affiliation | Investment, Issuer Affiliation Axis | `Investment, Issuer Affiliation Axis` | text | Filled on 5% of May rows. Values: unaffiliated, affiliated noncontrolled, affiliated controlled. |
| subsidiary | Investment Company, Nonconsolidated Subsidiary Axis | `Investment Company, Nonconsolidated Subsidiary Axis` | text | The unconsolidated JV a row belongs to. Filled in 24 filings (3,065 rows). Part of the holding key. Added by `combine.load_soi_all`. |

## Metadata columns (in every row)

| Column | Meaning |
|---|---|
| `release` | Which monthly file the row came from (2026_04 or 2026_05). Added by `combine.load_soi_all`. |
| `soi_row` | Row number inside that month's soi.tsv, starting at 0. Restarts each month, so cite `release` + `soi_row` together. |
| `adsh` | Filing accession number. |
| `cik` | The BDC's Central Index Key (SEC company ID). |
| `name` | The BDC's name. |
| `form` | 10-Q, 10-K or 10-K/A. |
| `period` | The filing's period end (from SUB). |
| `ddate` | The date of the fact; equals `period` for current rows. |
| `is_current` | True when `ddate` equals `period` (set by `split_periods`). |
| `cstm` | Whether the row uses custom tags (from SOI). |
| `inlineurl` | Link to the filing on EDGAR, for checking a row by hand. |

## Filing counts

| Month | Filings in SUB | After dropping amended (`prevrpt == "1"`) |
|---|---|---|
| 2026_04 | 4 | 4 |
| 2026_05 | 179 | 179 |
| 2026_06 | 0 | 0 |
| Total | 183 | 183 |

No filing is flagged as amended. April contains one 10-K/A (Equus Total Return, adsh 0001096906-26-000571), but the original 10-K it amends is not in our quarter, so nothing is superseded.

## Unmapped columns we reviewed

Decisions are based on current-period rows (ddate = period end) in our release: 2,178 in 2026_04 and 94,195 in 2026_05.

| Column | Needed? | Evidence and decision |
|---|---|---|
| `qtrs` | No | Duration of the fact in quarters. Mostly 0 (point-in-time), but 1–4 on 84 current rows in 2026_04 and 10,700 in 2026_05 (values over a period, such as income or roll-forward activity). Not needed to separate current from comparative rows: `split_periods` uses ddate = period end. Rows with qtrs > 0 are period values, which may help cleaning; we did not check whether they carry fair values. |
| `filed` | No | Filing date; already in SUB. |
| `Investment, Issuer Name Axis` | Not used; flagged | 4,032 current rows have no identifier but do have an issuer name (390 of 501 in 2026_04; 3,642 of 22,486 in 2026_05). `coalesce_holdings` drops rows without an identifier, so these may be holdings lost to a custom axis. A candidate fallback identifier; its effect on coverage was not measured. |
| `Investment Owned, Face Amount` | No | Fills a missing principal on only 407 current rows in 2026_05 and none in 2026_04. Principal is not used in reconciliation. |
| `Cash equivalents`, `Weighted Average Rate Domestic Deposit, Money Market` | No | `Cash equivalents` is filled on only 69 current rows. Cash and money-market lines are handled in cleaning (`rule_cash`). |
| `Investment, Issuer Affiliation [Extensible Enumeration]` | No (for reconciliation) | Fills affiliation on 1,061 current rows in 2026_05 that lack the affiliation axis, none in 2026_04. Not used in reconciliation; useful for the affiliation stretch goal. |

The other unmapped columns (derivatives, income, cash-flow lines; 239 in 2026_05, 30 in 2026_04) are not holdings fields.

## Holdings and conflicts (current period, 2026q2)

Current rows: 96,373. Rows without an identifier: 22,987 (dropped by `coalesce_holdings`; mostly candidates for totals and custom axes, handled in cleaning; 4,032 of them carry an issuer name, see above).

**Key.** A holding is filing + date + identifier + `subsidiary`. `subsidiary` is the `Investment Company, Nonconsolidated Subsidiary Axis`: 24 filings (17 rows in 2026_04, 3,048 in 2026_05) list the portfolios of unconsolidated joint ventures, so the same loan appears once per JV. Example: Oaktree Specialty Lending, adsh 0001414932-26-000012, AI Aqua Merger Sub first lien term loan at SOI rows 33570 (OCSI Glick JV LLC, fair value $1.744M) and 33799 (SLF JV I, $5.194M). Without `subsidiary` in the key these were merged as one holding and one value was discarded.

| Key | Holdings | Holdings with a conflict | Fair-value conflicts |
|---|---|---|---|
| filing + date + identifier (starter) | 64,549 | 479 | 200 |
| + subsidiary (ours) | 64,762 | 268 | 2 |

**Remaining conflicts by field:** pik_rate 257, interest_rate 8, cost 3, maturity 3, fair_value 2; principal, spread, pct_net_assets and the text fields 0.

**Resolution rule.** Within a holding, keep the first non-null value in SOI row order (`coalesce_holdings`), and record `n_conflicts`. The 2 fair-value conflicts are both "Blue Owl Cross-Strategy Opportunities LLC (BOCSO)", in Blue Owl Capital Corp (adsh 0001655888-26-000033, SOI rows 44735, 185194, 185819) and Blue Owl Credit Income Corp (adsh 0001812554-26-000027, rows 44737, 185196, 185821): values $378.0M and $24.7M. The rule keeps $378.0M. The sister funds report identical figures, so these may describe BOCSO as a whole rather than each fund's position; to be verified in the filings. pik_rate conflicts do not affect fair-value reconciliation and are left to the first-value rule.
## Source evidence extension (Part 3 follow-up, 2026-10-29)

The seven-rule pipeline optionally enriches canonical rows from the configuration
`source_evidence.input` and `source_evidence.documents`. The current inputs are
`data/source_evidence.json` and four original filing HTML snapshots in
`data/source_filings/`, tracked by `data/source_filings.dvc`. These supplement
SOI/NUM; they do not replace original amounts or supply guessed fair values.

| Field | Meaning |
|---|---|
| `source_role` | Curated role: schedule, cash_equivalent, rollforward_repeat or narrative_repeat |
| `source_scope` | investment, or outside_investment_total for the evidenced cash position |
| `source_instrument_key` | Curated identity linking a schedule fact to its repeated disclosure |
| `source_fact_id` | Original inline-XBRL fact ID |
| `source_document_sha256` | Fingerprint of the immutable original HTML snapshot |
| `source_url` | Original filing link |
| `source_decimals` | Precision read from the original XBRL fact, after respecting its scale |

`evidence.attach` binds annotations to filing, release, reporting date, identifier
and subsidiary in the canonical input. It verifies the snapshot, fact tag, CIK,
instant date, investment identifier, USD unit, numeric format and extracted value.
A stale or invalid annotation for a selected filing raises an error.
Unselected releases and unannotated filings receive no classification-based drop.

Coalescing preserves these fields and counts conflicting metadata. The guarded
cleaning rule requires conflict-free evidence, a unique schedule/repeat pair,
distinct fact IDs and matching filing/date/release/subsidiary/document.
Repeat rows with cost or principal are retained. The fair-value difference must
fit the combined precision intervals: 0.5 × (10^(-d1) + 10^(-d2)).
This is source precision, not a fixed dollar allowance or the 1% reconciliation
tolerance. The retained schedule amount is never rewritten.

The admitted panel retains source metadata where supplied, alongside `release`
and `source_rows` for every holding. The annotations are curated, not an
automatic semantic classifier, and do not imply human triage sign-off.
