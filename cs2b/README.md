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


## Configured input scope and Part 3 baseline

From `cs2b`, restore the versioned inputs and run the baseline:

```bash
dvc pull data/raw.dvc
python tools/baseline.py
```

`paths.release_dirs` resolves the scope for the configured baseline:
- Fixture mode always selects only the bundled fixture.
- In real-data mode, an explicit, non-empty `releases` list takes precedence.
- For one release, remove `releases` and set `release`, or supply a one-item list.
- Release IDs use `YYYY_MM` or `YYYYqN`. Duplicate IDs and invalid selections fail.
- List order determines precedence: the last listed copy of a repeated filing
  supplies its SUB, SOI and NUM records. Each holding retains its `release` and
  source-row numbers. Use chronological order when the latest release should win.

The command verifies recorded ZIP hashes and sizes and requires selected ZIPs in
`data/manifest.json`. It does not download new releases, poll the SEC, or update
DVC metadata. New data must first be acquired, recorded in the manifest, and
versioned with DVC. An empty SOI is allowed for an empty SUB; missing SOI with
current filings fails rather than silently reducing coverage. An entirely empty
selection fails with a diagnostic rather than producing a misleading baseline.

Outputs are `reports/baseline.json`, `reports/baseline_reconciliation.csv`, and
`reports/baseline_diagnostics.csv`. They use the two starter cleaning rules and
are not the final panel or completed triage. The existing single-directory
`run_baseline` API remains available for the starter notebooks and smoke tool.
Those tools and the final self-check still use a single release; quarter-wide
final reporting/checker integration belongs to subsequent Part 3 work.

Input loading is centralized in `combine.load_inputs`, which reuses the existing
combined table loaders and selects consistent filing copies across SUB/SOI/NUM.
It does not classify periods, clean holdings or reconcile totals. `pipeline.run_baseline`
coordinates those steps and accepts an explicit rules list, defaulting to the
existing two starter rules when none is supplied.
