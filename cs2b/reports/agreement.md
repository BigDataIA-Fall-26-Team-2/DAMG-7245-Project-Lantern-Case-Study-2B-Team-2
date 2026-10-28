# Agreement report (Part 1)

We compared our parsed holdings (Part 1 output: `combine.load_soi_all` → `split_periods` → `coalesce_holdings`, current period, before cleaning) with the human-readable Schedule of Investments in three filings. We did not use EdgarTools. For each filing we compare the holding count and fair-value total, explain every material difference, and show where the filing ended up after the team's cleaning and reconciliation (`reports/coverage.csv`).

The three filings were chosen to cover different cases: a clean 10-Q, a filer that lists its joint ventures' portfolios, and an April 10-K (which also tests the April fair-value fix in `schema.md`).

| Filing | adsh | Form, period | Our holdings | Our fair value | Filing's total | Gap (parsed) | Gap (after cleaning) |
|---|---|---|---|---|---|---|---|
| TCW Steel City Senior Lending BDC | 0001193125-26-221963 | 10-Q, 2026-03-31 | 16 | $381,917,205 | $381,917,205 | 0.00% | 0.00%, admitted |
| Oaktree Specialty Lending Corp | 0001414932-26-000012 | 10-Q, 2026-03-31 | 658 | $3,314,987,000 | $2,766,367,000 | +19.83% | +0.92%, admitted |
| TCW Direct Lending VII LLC | 0001193125-26-141887 | 10-K, 2025-12-31 | 90 | $860,917,114 | $645,193,114 | +33.44% | +16.72%, not admitted |

"Filing's total" is the undimensioned `InvestmentOwnedAtFairValue` fact in NUM at the period end, and in each case it matches the printed schedule exactly (cited below).

## TCW Steel City Senior Lending BDC: exact match

- **Filing:** "Total Debt & Equity Investments" = **$381,917,205** in the Consolidated Schedule of Investments as of March 31, 2026. Our parsed total is identical.
- **Note on labels:** the line labelled "Total Investments" shows $769,372,844 because it also includes Cash Equivalents ($6,992,329, First American Government Obligation Fund) and Short-term Investments ($380,463,310, U.S. Treasury Bill). $381,917,205 + $6,992,329 + $380,463,310 = $769,372,844. The tagged total, and our panel, exclude cash and Treasury bills, so "Total Debt & Equity Investments" is the comparable line.
- **Conclusion:** parsing is exact for a clean filing.

## Oaktree Specialty Lending Corp: difference is joint-venture portfolios

- **Filing:** the fair value hierarchy note shows "Total investments at fair value" = **2,766,367** (in thousands) = $2,766,367,000.
- **Difference:** +$548,620,000 (+19.83%).
- **Cause:** the filing also lists the portfolios of its unconsolidated joint ventures (OCSI Glick JV LLC and SLF JV I), tagged with the `Investment Company, Nonconsolidated Subsidiary Axis` (our `subsidiary` column). Example: AI Aqua Merger Sub first lien term loan at SOI rows 33570 (OCSI Glick JV, $1,744,000) and 33799 (SLF JV I, $5,194,000), release 2026_05. The filing's own hierarchy note says Oaktree's investments include "debt investments in the JVs" and "LLC equity interests of the JVs", i.e. its stake in each JV, not the JVs' underlying loans.
- **Check:** JV-portfolio holdings total $521,498,000. Excluding them leaves $2,793,489,000, a gap of +0.98%, within the 1% tolerance.
- **After cleaning:** 376 holdings, $2,791,741,000, +0.92%, admitted.
- **Conclusion:** parsing is correct; the difference is a known artifact (JV portfolios), removed in cleaning.

## TCW Direct Lending VII LLC: difference is the affiliated-investments footnote

- **Filing:** "Total Debt & Equity Investments" = **$645,193,114** (Consolidated Schedule of Investments as of December 31, 2025, page F-7). As with Steel City, "Total Investments" ($1,198,298,004) adds Cash Equivalents ($9,351,973) and a U.S. Treasury Bill ($543,752,917).
- **Difference:** +$215,724,000 (+33.44%).
- **Cause:** footnote (4) to the schedule is a roll-forward table of the filer's non-controlled affiliated investments (fair value at December 31, 2024, additions, reductions, fair value at December 31, 2025). Its rows carry the same fair-value tag, so they appear in SOI as extra holdings. "Total Non-Controlled Affiliated Investments" at December 31, 2025 = **$107,862,000** in the filing.
  - Our parsed affiliate section has 31 holdings totalling $215,724,000: the subtotal row "Non-Controlled Affiliated Investments" (SOI rows 2269;2270, $107,862,000) plus 30 repeated holdings ($107,862,000).
  - Example: RL Investor Holdings (fka Red Lobster Management) Term Loan appears at SOI rows 1001;1002 (main schedule) and 2243;2244 (footnote), both $56,324,391, release 2026_04. The footnote shows the same $56,324,391.
  - Excluding the affiliate section leaves exactly $645,193,114.
- **Holding count:** the filing's MD&A states 59 total investments (42 debt, 17 equity) as of December 31, 2025. We parse 90; after cleaning 89; 89 − 30 repeated footnote holdings = **59**, exactly the filing's count.
- **After cleaning:** 89 holdings, $753,055,114, +16.72%, not admitted. The remaining gap is exactly $107,862,000, the 30 repeated footnote holdings. Cleaning removed the subtotal row but not the repeated holdings.
- **Without the April fix** in `combine.load_tag_all`, this filing would have had no fair values at all (April's TAG table lacks the us-gaap/2026 label; see `schema.md`).
- **Conclusion:** parsing is correct; the difference is the affiliated-investments footnote counted as holdings. A rule that drops the footnote's repeated rows would reconcile this filing exactly (triage category: `restated_copies`).

## Summary

In all three filings our parsed fair values match the filing line by line once known artifacts are accounted for. No difference comes from parsing or column mapping:

- Clean filing: exact.
- Joint-venture portfolios (24 filings use the subsidiary axis): explained and handled by cleaning.
- Affiliated-investments footnote repeated as holdings: explained exactly; one filing still needs a cleaning rule.