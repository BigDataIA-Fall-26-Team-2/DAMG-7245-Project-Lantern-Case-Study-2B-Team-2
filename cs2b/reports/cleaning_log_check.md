# Cleaning-log examples, checked against the raw files

Each example in `reports/cleaning_log.csv` was opened in the raw `soi.tsv` of its month. `soi_row` is the 0-based row position in that file (as numbered by `combine.load_soi_all`), so the file line is the row number + 2 (header, 1-based lines). Regenerate with `PYTHONPATH=src python tools/verify_examples.py`.

| Rule | Example | What the row shows | Right filing |
|---|---|---|---|
| `rule_source_disclosures` | 0001193125-26-222738 / 2026_05 soi_row 50464 (file line 50466) | identifier "CO Acquisition Vehicle LLC"; fair value 17,370,481; ddate 2026-03-31 | yes |
| `rule_totals` | 0002037804-26-000010 / 2026_05 soi_row 33021 (file line 33023) | identifier "Total of Five Largest Portfolio Company Investments"; JV "NEWCRED Senior Loan Program I, LLC [Member]"; ddate 2026-03-31 | yes |
| `rule_cash` | 0001476765-26-000033 / 2026_05 soi_row 37364 (file line 37366) | identifier "Allspring Government Money Market Fund Select Share Class"; ddate 2026-03-31 | yes |
| `rule_commitment_rows` | 0001193125-26-222241 / 2026_05 soi_row 87437 (file line 87439) | identifier "Investments - non-controlled /non-affiliated First Lien Debt 7Ridge Investments Commitment Type Delayed Draw Commitment Expiration Date 7/7/2026"; ddate 2026-03-31 | yes |
| `rule_jv_portfolio` | 0001628280-26-027688 / 2026_04 soi_row 161 (file line 163) | identifier "Largest Portfolio Company Investment"; JV "Senior Direct Lending Program [Member]"; ddate 2026-03-31 | yes |
| `rule_issuer_subtotals` | 0001628280-26-027688 / 2026_04 soi_row 235 (file line 237) | identifier "Adonis Acquisition Holdings LLC and Adonis Acquisition Holdings Parent LLC"; fair value 25,100,000; ddate 2026-03-31 | yes |
| `rule_rollforward_copies` | 0001628280-26-027688 / 2026_04 soi_row 199 (file line 201) | identifier "ACAS Equity Holdings Corporation"; fair value 400,000; ddate 2026-03-31 | yes |

All examples open to a row of the named filing: **yes**.
