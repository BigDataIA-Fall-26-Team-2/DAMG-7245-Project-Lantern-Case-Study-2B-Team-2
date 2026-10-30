# Custom-tag recovery audit (stretch investigation)

Screened 3488 current-period USD instant custom NUM facts on InvestmentIdentifierAxis, across 39 filings.
Exact identifier/context candidates fill 34 missing current holding values in a COPY of the inputs. Existing configured rules are then rerun. Newly admitted filings: 0.
The production panel is unchanged. These candidates are not approved recovery mappings. The source investigation in docs/cleaning_log.md identifies the matching TCW facts as affiliate roll-forward ending balances, not additional schedule positions.

| Filing | Missing holdings matched | Candidate FV | Before gap | Counterfactual gap | Newly admitted? |
|---|---:|---:|---:|---:|---|
| 0001193125-26-141887 | 18 | 617,691,984.00 | +16.718% | +112.455% | False |
| 0001193125-26-221880 | 16 | 493,400,730.00 | +16.616% | +54.147% | False |

Cash/commitment/support tags cannot be substituted for investment fair value. Blue Owl fee-netted values concern holdings with an existing fair value; Goldman Sachs roll-forward identifiers do not match missing schedule holdings. Alternate standard `Investments` values are not custom-tag recovery and include subtotals.
Result: no verified custom-tag recovery/re-admission has been established for these releases. Do not claim the two bonus points as completed. A new source-supported mapping or different candidate is required; tests or a desired total cannot supply that evidence.
Reproduce: `python tools/audit_custom_fv.py` after `dvc repro`. See custom_tag_screen.csv, custom_tag_candidates.csv, custom_tag_counterfactual.csv and the existing source investigation for traceable details.
