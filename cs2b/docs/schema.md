# Canonical holdings schema

Release: 2026q2 = monthly SEC BDC ZIPs 2026_04, 2026_05, 2026_06 (2026_06 has no filings).
Mapping is by XBRL tag via `mapping.map_soi_columns`, using labels from the TAG tables of all three months (`combine.load_tag_all`), never by column position.

| Field | Source tag or axis | SOI column(s) in our release | Type | Notes |
|---|---|---|---|---|
| fair_value | InvestmentOwnedAtFairValue | `Investment Owned, Fair Value`; `Initial fair value of Investment` | float, USD | The us-gaap/2026 version of this tag carries the label "Initial fair value of Investment", and nearly all values sit in that column (May: 150,672 rows; April: 4,177 of 4,378); no row fills both. April's own TAG table lists only the older label, so per-month mapping found 0 April fair values. Fixed in `combine.load_tag_all`, which merges all months' TAG tables before mapping. |
| cost | InvestmentOwnedAtCost | `Investment Owned, Cost`; `Adjusted cost basis` | float, USD | Same label issue as fair_value (us-gaap/2026 label "Adjusted cost basis"); same fix. |
| principal | InvestmentOwnedBalancePrincipalAmount | `Investment Owned, Balance, Principal Amount` | float, USD | Filled on 52% of May rows. `Investment Owned, Face Amount` (unmapped) is a possible fallback, TBD. |
| interest_rate | InvestmentInterestRate | `Investment Interest Rate` | float, decimal | Median 0.087 (8.7%). Max 8.0, so some filers may report in percent units. Flag for cleaning. |
| spread | InvestmentBasisSpreadVariableRate | `Investment, Basis Spread, Variable Rate` | float, decimal | Median 0.05. Max 10.0, same units concern. |
| maturity | InvestmentMaturityDate | `Investment Maturity Date` | date | Already ISO (YYYY-MM-DD) in May; normalized by `load.norm_date`. |
| pik_rate | InvestmentInterestRatePaidInKind | `Investment, Interest Rate, Paid in Kind` | float, decimal | Filled on 6% of May rows. Max 7.5, units concern. |
| pct_net_assets | InvestmentOwnedPercentOfNetAssets | `Investment Owned, Net Assets, Percentage` | float, decimal | Median 0.002. Max 295.2, likely percent units or a total row. Flag for cleaning. |
| identifier | Investment, Identifier Axis | `Investment, Identifier Axis` | text | Filled on 76% of May rows; missing ones are candidates for totals or custom axes. Free text, format varies by filer. |
| investment_type | Investment Type Axis | `Investment Type Axis` | text | Filled on 9% of May rows. |
| industry | Industry Sector Axis | `Industry Sector Axis` | text | Filled on 11% of May rows. |
| affiliation | Investment, Issuer Affiliation Axis | `Investment, Issuer Affiliation Axis` | text | Filled on 5% of May rows. Values: unaffiliated, affiliated noncontrolled, affiliated controlled. |

## Filing counts

| Month | Filings in SUB | After dropping amended (`prevrpt == "1"`) |
|---|---|---|
| 2026_04 | 4 | 4 |
| 2026_05 | 179 | 179 |
| 2026_06 | 0 | 0 |
| Total | 183 | 183 |

No filing is flagged as amended. April contains one 10-K/A (Equus Total Return, adsh 0001096906-26-000571), but the original 10-K it amends is not in our quarter, so nothing is superseded.

## Unmapped columns we reviewed

| Column | Needed? | Why |
|---|---|---|
| `qtrs` | TBD | Duration of the fact; may help separate current from comparative rows. |
| `filed` | No (metadata) | Filing date; already in SUB. |
| `Investment, Issuer Name Axis` | Maybe | Fallback identifier where Identifier Axis is blank. |
| `Investment Owned, Face Amount` | Maybe | Possible principal fallback. |
| `Cash equivalents`, `Weighted Average Rate Domestic Deposit, Money Market` | For cleaning | Cash and money-market artifact (Part 2). |
| `Investment, Issuer Affiliation [Extensible Enumeration]` | Maybe | Affiliation fallback; affiliation stretch goal. |

The other unmapped columns (derivatives, income, cash-flow lines; 239 in May, 30 in April) are not holdings fields.


## Holdings and conflicts (current period, 2026q2)

Current rows: 96,373. Rows without an identifier: 22,987 (dropped by `coalesce_holdings`; mostly candidates for totals and custom axes, handled in cleaning).

**Key.** A holding is filing + date + identifier + `subsidiary`. `subsidiary` is the `Investment Company, Nonconsolidated Subsidiary Axis`: 24 filings (17 rows in 2026_04, 3,048 in 2026_05) list the portfolios of unconsolidated joint ventures, so the same loan appears once per JV. Example: Oaktree Specialty Lending, adsh 0001414932-26-000012, AI Aqua Merger Sub first lien term loan at SOI rows 33570 (OCSI Glick JV LLC, fair value $1.744M) and 33799 (SLF JV I, $5.194M). Without `subsidiary` in the key these were merged as one holding and one value was discarded.

| Key | Holdings | Holdings with a conflict | Fair-value conflicts |
|---|---|---|---|
| filing + date + identifier (starter) | 64,549 | 479 | 200 |
| + subsidiary (ours) | 64,762 | 268 | 2 |

**Remaining conflicts by field:** pik_rate 257, interest_rate 8, cost 3, maturity 3, fair_value 2; principal, spread, pct_net_assets and the text fields 0.

**Resolution rule.** Within a holding, keep the first non-null value in SOI row order (`coalesce_holdings`), and record `n_conflicts`. The 2 fair-value conflicts are both "Blue Owl Cross-Strategy Opportunities LLC (BOCSO)", in Blue Owl Capital Corp (adsh 0001655888-26-000033, SOI rows 44735, 185194, 185819) and Blue Owl Credit Income Corp (adsh 0001812554-26-000027, rows 44737, 185196, 185821): values $378.0M and $24.7M. The rule keeps $378.0M. The sister funds report identical figures, so these may describe BOCSO as a whole rather than each fund's position; to be verified in the filings. pik_rate conflicts do not affect fair-value reconciliation and are left to the first-value rule.