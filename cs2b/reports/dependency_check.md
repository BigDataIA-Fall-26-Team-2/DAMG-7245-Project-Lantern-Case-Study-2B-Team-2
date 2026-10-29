# Part 4: Dependency check

## What we did

We checked our panel against the human-readable schedules in the filings. We sampled 20 holdings across 10 filings with `scripts/spot_check_sample.py`: the 5 largest filings by fair value plus 5 more at random (seed 7), and 2 holdings from each, the largest and one at random. The same seed gives the same sample every run.

For each holding we opened the filing from its `filing_url`, found the line in the schedule dated March 31, 2026, and compared fair value and principal with the panel. Ares Capital reports in millions, all other filers in thousands, so we converted before comparing. Every result is in `reports/spot_check.csv`, one row per holding, with the adsh, release, SOI source row, the filing values and a note.

We did not use EdgarTools. The comparison is only between our panel and the filings.

## What we observed

19 of 20 holdings match the filing on both fair value and principal. 1 holding is not a real holding.

### 1. A row from the unfunded commitments table is in the panel

T Series BDC (adsh 0001193125-26-219405, SOI row 97935). The panel has a holding named "Cerity Partners, LLC Commitment Type Revolver Commitment Expiration Date 07/28/2031" with no fair value and no principal. In the filing the schedule lists Cerity Partners only as three First Lien Debt rows. The Revolver line with expiry 07/28/2031 is in the unfunded commitments table (unfunded amount 440 thousand, fair value shown as a dash). So the panel source is wrong here, not the filing: the SOI file carries these commitment lines with an investment identifier, and none of our cleaning rules drops them.

We checked the whole panel for identifiers with "Commitment Type" or "Commitment Expiration". There are 1,788 such rows in 9 filings:

- Antares Private Credit Fund 370, Antares Strategic Credit Fund 375, Antares Strategic Credit Fund II 100, North Haven Private Income Fund A 211: all carry a fair value, all negative, total -14.3 million, at most 0.21% of each filer's panel fair value
- LGAM Private Credit 199, MSD Investment Corp. 75, SL Investment Fund II 134, T Series BDC 271, Vista Credit Strategic Lending 53: none carry a fair value

The dollar effect is inside the 1% tolerance, so no filing was admitted because of these rows. They do add holdings that are not holdings. We did not check whether the negative values at the 4 filers also appear on a schedule line, which would count them twice.

### 2. Principal has no currency

Apollo Debt Solutions BDC (adsh 0001193125-26-215667, SOI row 77827). SPARKLE BIDCO LIMITED, First Lien Term Loan SONIA+525, 10/14/2032. The filing shows par £87,479 thousand and fair value $114,051 thousand. The panel has the same two numbers, 87,479,000 and 114,051,000.

Blackstone Secured Lending Fund (adsh 0001736035-26-000010, SOI row 158717). Spectrum Safety Solutions Purchaser, LLC, E+4.50%, 7/1/2030. The filing shows principal EUR 1,806 thousand and fair value $2,087 thousand. The panel has 1,806,000 and 2,087,000.

The values are right, but the panel principal has no currency column, so a user reads both as dollars. Then price, 100 × fair value / principal, comes out about 130 for SPARKLE BIDCO and about 116 for Spectrum, which is wrong. The Apollo schedule has more non-dollar lines, for example EHC Holdings Holdco (£) and Opseo Holding (€), so this is not one row.

### 3. Lines that looked odd but are correct

- Unfunded revolvers: Lafayette Square SMG Operating (adsh 0001628280-26-032846, SOI row 157379) shows a dash for principal and fair value, panel has 0. Oaktree Centralsquare First Lien Revolver (adsh 0001414932-26-000012, SOI row 48395) shows fair value (16) thousand, panel has -16,000.
- Equity with no principal: Ares Capital Ivy Hill member interest (SOI row 1777), Ares Capital High Street Buyer Series A preferred units (SOI row 1639), New Mountain NMFC Senior Loan Program III membership interest (SOI row 124055). The filing shows no principal, panel has none.
- Same name repeated: when a filer lists several lines with the same text, the identifier ends in a number that is the position of the line. High Street "Series A preferred units 3" is the third of four such rows, PPW Aero "One stop 6" the sixth of seven, Daxko "First lien 3" the third of three. All matched the line at that position.

We also saw 2,098 panel rows with no fair value in 57 filings. 732 of them are the commitment rows above. We did not look into the rest.

## What we understood

For the holdings we sampled, the panel values trace correctly to the filings, after converting units. The two problems are about what the panel means, not about wrong numbers: commitment lines sit in the panel as holdings, and principal is stored without its currency. Anyone computing holding counts or prices from the panel should know both. A cleaning rule for the commitment rows and a currency column for principal would fix them.
