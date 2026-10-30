# Affiliation reconciliation (stretch)

Compares cleaned holdings with current USD instant InvestmentOwnedAtFairValue NUM facts whose sole dimension is InvestmentIssuerAffiliationAxis.
Holding membership comes only from standard affiliation enumeration facts on the holding’s own SOI source rows. No name guessing or forward filling.

267 reported category totals across 134 filings. Status counts: {'incomplete_classification_or_values': 266, 'matched': 1}.
Unclassified holdings prevent a category pass. Identical duplicate totals are accepted; conflicting totals are unusable. Missing reported categories are not invented.
This optional comparison does not alter the overall filing admission decision.

| Filing | Category | Holdings FV | Filed category FV | Result |
|---|---|---:|---:|---|
| 0001104659-26-061177 | unaffiliated | 387,669,000.00 | 387,669,000.00 | matched |

All results, including incomplete classifications and SOI row provenance, are in `affiliation.csv`. Raw references are in the selected release’s `datasets/num.tsv`; match accession, SUB period, tag, member, USD, qtrs=0, dimn=1.
Reproduce with `python scripts/affiliation.py` or `dvc repro affiliation`.
