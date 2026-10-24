# Lab 2B starter kit: Look-Through (SEC BDC data sets)

DAMG 7245, Fall 2026. Companion to the Tool Tutorial Part 2B deck, the BDC Primer and Case Study 2B.

## Setup (10 minutes)
Copy this folder into your team's Case Study 1 repository as `cs2b/`, and run everything from inside it.
```
cd cs2b
python -m venv .venv && source .venv/bin/activate      # Python 3.10 or later
pip install -r requirements.txt
jupyter lab                                             # open notebooks/00_setup.ipynb
```
Then set `sec.user_agent` (your name and email) and your team's `release` in `params.yaml`.

## Work through, in order
| Notebook | Step |
|---|---|
| 00_setup | Environment, parameters, tests |
| 01_primer_exercise | One holding, from flat file to filing |
| 02_acquire | Download your release, manifest, DVC (switches you to real data) |
| 03_raw_parse | SUB, TAG, NUM and SOI; map columns by tag |
| 04_periods_and_dimensions | Dates, current vs comparative schedules, segments, coalescing |
| 05_clean | Find artifacts, write rules, keep a cleaning log |
| 06_reconcile | Reconcile to filed totals, coverage, triage, outputs, self-check |
| 07_verify_dependency | Spot-check against the filings; optional EdgarTools comparison |
| 08_pipeline_and_economics | Tests that fail, timing, unit economics, DVC pipeline |

You start in **fixture mode** (`data.use_fixture: true`): a synthetic release in the SEC's layout, with fictional BDCs, so everything runs offline. Notebook 02 switches you to your real release.

## Checks
```
python tests/run_tests.py                 # or: pytest -q
python tools/run_notebooks.py             # runs every notebook's code in order
PYTHONPATH=src python -m lookthrough.check   # Case Study 2B self-check on your outputs
python tools/smoke_real.py <release> "Name email"   # baseline on any real release (needs network)
```

## Layout
`src/lookthrough/` helpers (paths, acquire, load, mapping, holdings, clean, reconcile, pipeline, report, tables, check);
`data/fixture/` the synthetic release (rebuild with `python tools/make_fixture.py`); `data/raw/` your release (DVC, never Git);
`outputs/panel/` the reconciled panel; `reports/` coverage, triage, cleaning log, spot checks; `docs/` schema and pipeline notes.

## Data
Public data only: the SEC BDC data sets (https://www.sec.gov/data-research/sec-markets-data/bdc-data-sets) and the SEC BDC readme (https://www.sec.gov/files/bdc_readme.pdf). Fixture data is synthetic.
