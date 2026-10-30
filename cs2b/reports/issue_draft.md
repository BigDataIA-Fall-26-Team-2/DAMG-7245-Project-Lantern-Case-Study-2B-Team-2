# Issue drafts

Data and library issues we found in Case Study 2B, written up with evidence, ready to send once grades are returned. Every claim names the filing (adsh) and the SOI row. To add an issue, copy the template at the end and give it the next number.

## Issue 1: soi.tsv does not show the currency of principal amounts

Author: Guna
To: SEC Division of Economic and Risk Analysis, BDC data sets team
Data set: BDC data sets, release 2026_05 (soi.tsv, num.tsv)

What we found: in soi.tsv the principal amount carries only the number, with no unit of measure. For loans whose principal is in a foreign currency, the principal looks like a dollar amount, while the fair value of the same holding is in dollars. Price, computed as fair value divided by principal, is then wrong for these holdings.

Evidence:
1. Apollo Debt Solutions BDC, adsh 0001193125-26-215667, soi.tsv row 77827. SPARKLE BIDCO LIMITED, First Lien Term Loan, SONIA + 5.25%, maturity 10/14/2032. The filing's schedule shows par £87,479 thousand and fair value $114,051 thousand. soi.tsv has principal 87,479,000 and fair value 114,051,000 with no currency, so the price reads as 130.4.
2. Blackstone Secured Lending Fund, adsh 0001736035-26-000010, soi.tsv row 158717. Spectrum Safety Solutions Purchaser, LLC, E + 4.50%, maturity 7/1/2030. The filing shows principal EUR 1,806 thousand and fair value $2,087 thousand. soi.tsv has 1,806,000 and 2,087,000, so the price reads as 115.6.

The same Apollo schedule has more holdings like this, for example EHC Holdings Holdco Limited (£) and Opseo Holding B.V. (€).

What would help: add the unit of measure for each monetary column to soi.tsv, as num.tsv already has a uom field for each fact, or say in the readme that SOI amounts can be in different currencies and must be joined to num.tsv for the unit.

How to reproduce: open soi.tsv of release 2026_05 at the rows above and compare the principal with the schedule of investments in each filing.

## Issue 2: unit counts of equity tagged as principal amount

Author: Guna
To: SEC Division of Economic and Risk Analysis, BDC data sets team (data quality note)
Data set: BDC data sets, release 2026_05 (soi.tsv)

What we found: some filers use one schedule column for two things, "Par Amount / Quantity" or "Par/Shares": for loans it is the amount owed, for equity it is the number of units or shares. They tag that column as InvestmentOwnedBalancePrincipalAmount for every row, so in soi.tsv equity holdings carry a "principal" that is really a count. Users who treat any holding with a principal as debt classify this equity as a loan.

Evidence:
1. Great Elm Capital Corp., adsh 0001193125-26-204228, soi.tsv rows 50077;50078. CLO Formation JV, LLC, Common Equity. The filing's column is "Par Amount / Quantity" and shows 166 units with fair value $37,590 thousand. soi.tsv has principal 166 and fair value 37,590,000.
2. Across release 2026_05 and our admitted panel, 574 equity holdings in 43 filings carry a principal: unit counts (for example 2X LLC Investors LP Class A Units, 43,875), zeros (Monroe Capital Income Plus writes 0 for its equity lines) and share counts on preferred shares (New Mountain, ACI Parent Inc. preferred shares, 20,249,000).

What would help: a note in the readme that the principal tag can hold quantities for equity holdings, or a flag in soi.tsv when a principal amount belongs to an equity instrument.

How to reproduce: open soi.tsv of release 2026_05 at the rows above and compare with the schedule of investments in the filing.

## Issue 3: affiliate roll-forward rows appear in soi.tsv as holdings

Author: Dhruvi
To: SEC Division of Economic and Risk Analysis, BDC data sets team
Data set: BDC data sets, release 2026_05 (soi.tsv)

What we found: many filers add a roll-forward table for affiliated and controlled investments (opening value, purchases, sales, closing value). soi.tsv loads these rows as if they were schedule holdings, with nothing that marks them apart. The same loan then appears twice, so summing soi.tsv overstates the filing.

Evidence:
1. FS KKR Capital Corp., Wittur: schedule row 171216 and its roll-forward copy, row 171222, carry the same holding and value. Full adsh and release are in docs/cleaning_log.md (rule_rollforward_copies).
2. Across our quarter, 319 copy rows in 20 filings. Removing them moved Main Street Capital from +12.82% to -0.04% against its filed total.

What would help: a flag or separate axis in soi.tsv for roll-forward table rows, or a note in the readme that these tables are included.

How to reproduce: open soi.tsv at the rows above and compare with the schedule of investments and the affiliate roll-forward table in the filing.

## Issue 4: unfunded-commitment table rows appear in soi.tsv as holdings

Author: Dhruvi
To: SEC Division of Economic and Risk Analysis, BDC data sets team
Data set: BDC data sets, release 2026_05 (soi.tsv)

What we found: rows from the unfunded-commitments table are loaded into soi.tsv as holdings. Their identifier holds "Commitment Type" and "Commitment Expiration Date", and they have no cost or principal. These are promises to lend, not loans, so they should not be counted with the schedule.

Evidence:
1. T Series Middle Market Loan Fund, release 2026_05, SOI row 97935: Cerity Partners Revolver, Commitment Expiration Date 07/28/2031, no fair value or principal. In the filing this line is only in the unfunded commitments table. Found in Guna's spot check (reports/dependency_check.md).
2. Across our quarter, 2,357 such rows in 11 filings. Full adsh list is in docs/cleaning_log.md (rule_commitment_rows).

What would help: a flag in soi.tsv for rows that come from the commitments table, or a readme note that they are included.

How to reproduce: open soi.tsv of release 2026_05 at row 97935 and compare with the filing's schedule and its unfunded commitments table.

## Issue 5: fair value reported under a generic tag is missing from soi.tsv

Author: Dhruvi
To: SEC Division of Economic and Risk Analysis, BDC data sets team
Data set: BDC data sets, release 2026_05 (soi.tsv, num.tsv)

What we found: soi.tsv fills fair value only from the standard fair-value tag. When a filer reports a holding's value under the generic Investments tag instead, the fair-value column is empty, and the filing looks short of its own reported total.

Evidence:
1. Lord Abbett Private Credit Fund S, release 2026_05, SOI row 17151 (its joint-venture investment). The filing is short by exactly this holding, $21.608M (a -5.66% gap). Details in docs/cleaning_log.md (custom-tag recovery).
2. We did not add a general fallback: across the quarter, 3,488 custom-tagged facts were commitments, fee adjustments and roll-forward balances, and recovering them double-counted (TCW Direct Lending VII moved from +16.7% to +112%).

What would help: a readme note listing which tags feed the fair-value column, or a column naming the source tag for each value.

How to reproduce: open soi.tsv of release 2026_05 at row 17151, then look up the same holding in num.tsv.

## Template for a new issue

Copy from here, give it the next number, and fill every line.

## Issue N: one-line title

Author:
To: (SEC data set team, or the maintainer of the library)
Data set or library: (release, file, or library and version)

What we found:

Evidence: (adsh and SOI row for every example, and what the filing itself shows)

What would help:

How to reproduce:
