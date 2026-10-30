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
