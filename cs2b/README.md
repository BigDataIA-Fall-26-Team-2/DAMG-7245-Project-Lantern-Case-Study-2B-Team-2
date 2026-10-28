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
`reports/baseline_diagnostics.csv`. They use the ordered `cleaning.rules` selection (the five reviewed Part 2 rules) and
are not the final panel or completed triage. The existing single-directory
`run_baseline` API remains available for the starter notebooks and smoke tool.
The original notebooks and smoke tool still use one directory. The self-check
uses the same configured release mapping as the baseline and report generation.

Input loading is centralized in `combine.load_inputs`, which reuses the existing
combined table loaders and selects consistent filing copies across SUB/SOI/NUM.
It does not classify periods, clean holdings or reconcile totals. `pipeline.run_baseline`
coordinates those steps and accepts an explicit rules list, defaulting to the
five rules in `clean.RULES` when none is supplied.


### Reconciliation safeguards

Filed totals must be undimensioned, USD, instant (`qtrs=0`) facts at the SUB
period end. Identical repeated values are accepted; conflicting or nonfinite
values leave the total unresolved and carry `filed_total_status` for review.
Zero/negative totals cannot support percentage-based admission.

Admission uses the absolute fractional gap and includes the exact configured
boundary. Missing totals, no holdings, all-missing values and infinite holding
values produce a blank gap and are not admitted. Partially missing fair values
remain counted in `missing_fv`; the known-value sum is still compared using the
handout's tolerance, without inventing values for missing holdings.

Coverage retains every attempted filing. It also identifies SUB filings without
SOI rows and counts attempts without a usable filed total. Dollar coverage uses
only known positive filed totals: dollars for unresolved filings are unknown,
not estimated as zero. These safeguards do not replace filing-level triage or
human-readable spot checks. Cleaning integration is complete; filing-level evidence review remains pending.


### Generate the preliminary panel and reports

```bash
python tools/baseline.py --write-outputs
```

This uses the configured cleaning rules, the five reviewed Part 2 rules. It produces
`outputs/panel/holdings.parquet`, `reports/coverage.csv`, `reports/coverage.json`,
`reports/coverage.md`, `reports/triage.md`, and `reports/cleaning_log.csv`.
The panel retains `is_debt`, `release` and semicolon-separated `source_rows`, includes only
current holdings of admitted filings, and is checked against admitted totals
before being written. Parquet support is required; there is no silent CSV fallback.
The CSV uses the eight handout columns. JSON and Markdown use the same coverage
calculation, including attempted filings without usable totals and the separate
list of SUB filings without SOI rows. The panel is DVC-tracked by
`outputs/panel.dvc`; restore the committed artifact with `dvc pull outputs/panel.dvc`.
After intentional regeneration, run `dvc add outputs/panel` and
`dvc push outputs/panel.dvc`, then commit the updated pointer with the reports.
Generating reports alone does not publish them to S3. Part 5's `dvc repro` stage
integration remains separate team work.

Human triage belongs in the Git-tracked CSV configured by `triage.input`
(default `data/triage.csv`), not in generated reports. The supplied file is an
empty template; no real filing has been marked reviewed by this implementation.

Each input row contains:
- `adsh`: the filing accession number (one unique row per filing).
- `triage_category`: one of the handout's allowed categories.
- `evidence`: the observed facts supporting the explanation, with citations.
- `example`: filing and relevant release/SOI row references; explain explicitly
  if a row example is unavailable (for example, no identifiable holding rows).
- `fix_or_reason`: the applied fix, or why the filing remains unresolved.
- `review_status`: blank, `draft`, or `reviewed`. Mark reviewed only after checking
  the evidence. A matching sum alone does not establish a correct explanation.
- `reviewed_holdings_fv`, `reviewed_filed_fv`: the numeric totals being reviewed,
  without currency symbols or commas; leave blank only when the value is missing.

Report generation never changes this input. It preserves notes for filings
outside the current run as well. Excluded filings without complete, reviewed
entries receive `to_triage`, an INCOMPLETE marker and a count in `coverage.json`.
If either total changes by more than one cent, the saved entry requires re-review.
These are completeness checks, not automated verification of human claims; changes
in holdings that leave totals unchanged still require human review. Entries for
admitted filings remain saved but their coverage category is blank.

The self-check supports the configured releases; triage review remains pending. Preliminary reports are not a finished submission.


### Rule selection and multi-release validation

`cleaning.rules` in `params.yaml` lists the `rule_*` functions to run, in order.
The command resolves every name before processing data; a missing, duplicate,
empty or invalid selection is an error. There is no fallback that silently skips
an unavailable Part 2 rule. The selection is `rule_totals`, `rule_cash`, `rule_jv_portfolio`,
`rule_issuer_subtotals`, `rule_rollforward_copies`, in that order.
The pipeline adds roll-forward opening-balance evidence before filtering to current
holdings, then applies the rules and adds the debt flag. `tools/rule_impact.py`
uses the same input selection and configured rules.
The low-level `run_baseline(..., rules=...)` interface remains available to notebooks
and tools; callers using parameters should pass `pipeline.configured_rules(params)`.

Run the checks from `cs2b`:

```bash
PYTHONPATH=src python -m lookthrough.check
```

The ten checks now read the same selected SUB/SOI/NUM inputs as the baseline,
including the same winner for repeated filings. A multi-release panel must carry
`release`; sampled provenance uses `(release, source_rows)` and verifies the filing,
current period and fair value. A value absent from SOI is not automatically accepted
as NUM recovery: a future recovery implementation needs an evidenced validation path.

The checker rejects missing reported totals substituted for known values, blank or
incorrect gaps, extra/duplicate coverage rows and incomplete/stale triage evidence.
An allowed category alone is insufficient: the separate input must contain a reviewed
explanation, example and matching totals. It remains a structural checker, not a
replacement for opening filings and evaluating the claims. Incomplete real-data triage
is expected to fail until those investigations are performed; do not relabel drafts
as reviewed merely to pass the checker.


### Integrated Part 3 run (2026-10-27)

With PR #3 merged, all five rules admit 90 of 177 attempted filings (50.8%)
and cover $235,924,621,309 of $542,175,875,908 known filed dollars (43.5%).
The panel contains 34,755 holdings with 37,648 raw SOI row references, retaining
3,493 holdings flagged as non-debt. Eight attempts lack a usable filed total;
six SUB filings have no SOI rows and are reported separately.

The 87 excluded filings still require evidence-backed triage. No entries have
been falsely marked reviewed to pass acceptance. This is a preliminary artifact;
the triage acceptance check remains failing until those investigations are complete.
