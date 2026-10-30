# Part 4: Dependency check

## What we did

We checked our panel against the human-readable schedules in the filings. `scripts/spot_check_sample.py` draws 20 holdings across 10 filings: the 5 largest admitted filings by fair value, 5 more at random (seed 7), and 2 holdings from each, the largest and one at random. The committed CSVs freeze the original reviewed selection. A rerun under pandas 3.1 selected two different holdings because the old sampler did not resolve equal fair values consistently. The sampler now sorts ties by accession, release, identifier and source rows, and uses seeded SHA-256 ranks for random selections. Future draws are independent of input order and pandas/NumPy random generators; they are new samples and need their own reviews. The corrected script writes `reports/spot_check_sample_new.csv` by default and never overwrites the reviewed `reports/spot_check.csv`.

For each holding we opened the filing from its `filing_url`, found the line in the schedule dated 31 March 2026, and compared fair value and principal with the panel. Units differ by filer: Ares Capital reports in millions, BlackRock Direct Lending and Onex in dollars, the others in thousands, so we converted before comparing. Every result is in `reports/spot_check.csv`, one row per holding, with adsh, release, SOI source rows, the filing values and a note.

We did this twice. The first sample was drawn when 90 of 177 filings were admitted. After PR #41 (commitment rule) and PR #42 (triage fixes, 101 of 177 admitted) the panel changed, so we drew the sample again. 11 of the 20 holdings were the same with the same values, and we kept those reviews. 9 holdings were new and we checked them by hand. All 20 reviewed holdings and their values were revalidated against the submitted panel. The reviewed CSV and its companion sample remain frozen; they are not claimed to be the output of the corrected sampling algorithm. To create a fresh draw without replacing this evidence, use `python scripts/spot_check_sample.py --out reports/spot_check_sample_new.csv`.

We did not use EdgarTools. The comparison is only between our panel and the filings.

## What we observed

19 of 20 holdings match the filing on both fair value and principal. 1 holding matches on fair value but its principal is not a principal.

### 1. Rows from the unfunded commitments table (found in the first sample, now fixed)

In the first sample, T Series BDC (adsh 0001193125-26-219405, SOI row 97935) had a holding named "Cerity Partners, LLC Commitment Type Revolver Commitment Expiration Date 07/28/2031" with no fair value and no principal. In the filing this line is in the unfunded commitments table (unfunded amount 440 thousand), not in the schedule. At that time 1,788 panel rows in 9 filings had this wording. PR #41 added `rule_commitment_rows`, which drops these rows, and the line is no longer in the panel. In the new sample T Series gives Smarsh, Inc. instead (SOI row 57780), which matches.

### 2. Principal has no currency

Apollo Debt Solutions BDC (adsh 0001193125-26-215667, SOI row 77827). SPARKLE BIDCO LIMITED, First Lien Term Loan SONIA+525, 10/14/2032. The filing shows par £87,479 thousand and fair value $114,051 thousand. The panel has 87,479,000 and 114,051,000.

Blackstone Secured Lending Fund (adsh 0001736035-26-000010, SOI row 158717). Spectrum Safety Solutions Purchaser, LLC, E+4.50%, 7/1/2030. The filing shows principal EUR 1,806 thousand and fair value $2,087 thousand. The panel has 1,806,000 and 2,087,000.

The values are right, but the panel principal has no currency column, so a user reads both as dollars. Price, 100 × fair value / principal, comes out about 130 and 116, which is wrong. The Apollo schedule has more lines like this, for example EHC Holdings Holdco (£) and Opseo Holding (€).

### 3. Principal holds a quantity of units for equity

Great Elm Capital Corp. (adsh 0001193125-26-204228, SOI rows 50077;50078). CLO Formation JV, LLC, Common Equity. The filing column is "Par Amount / Quantity". For loans it is par, for equity it is the number of units. The filing shows 166 units and fair value 37,590 thousand. The panel has fair value 37,590,000, which matches, and principal 166. Because principal is filled, `is_debt` is True for this equity holding, and its price is meaningless. Onex uses a similar "Par/Shares" column, but our Onex holdings are loans, so they are fine.

### 4. Lines that looked odd but are correct

- Comparative copies: for BlackRock Bluefin Holding (SOI row 62057) and Onex IMB Midco (SOI rows 131112;131113) the first search hit was the 31 December 2025 line, with a different rate and value. The 31 March line matched the panel. The current-period split works.
- Negative value on a drawn revolver: Onex IMB Midco Revolving Loan shows par 255,109 and fair value (74,594), as in the panel. The line is on the next page of the schedule.
- Unfunded revolvers: Oaktree Centralsquare First Lien Revolver shows fair value (16) thousand, panel -16,000. Lafayette SMG showed a dash, panel 0 (first sample).
- Equity with no principal: Ares Capital Ivy Hill member interest (SOI row 1777) and High Street Buyer preferred units (SOI row 1639). No principal in the filing or the panel.
- Same name repeated: the identifier ends in a number or word that tells the lines apart, but not always by position. High Street "Series A preferred units 3" is the third of four rows. T Series "Smarsh ... Two" is the third of three Smarsh lines. In every case the values pointed to one line only.
- Group total next to a holding: AGL Maverick Power is the only holding in its industry group, so the filing shows it bold with the group total. The panel keeps it once. The Spotless Brands subtotal (39,923 / 39,811) is not in the panel.

## What we understood

For the holdings we sampled, fair values trace correctly to the filings after converting units, and the current period is picked correctly where the comparative schedule repeats a holding. The problems are about what the panel columns mean, not wrong fair values: principal is stored without its currency, and for some equity the principal field holds a quantity of units. Anyone computing prices or debt statistics from the panel should know both. One problem we found, commitment rows counted as holdings, is now fixed by a cleaning rule. A currency column for principal, and a rule that clears principal for equity rows on a "Quantity" or "Shares" column, would fix the other two.
