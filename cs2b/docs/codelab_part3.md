# Part 3: Reconciliation, coverage and triage

Goal: Compare each filing’s cleaned investments with its independent reported total, publish passing holdings, and explain exclusions with source evidence. Owner: Sai Lokesh Reddy Nandavarapu.

| Step | Input | Output |
|---|---|---|
| Reconcile | Cleaned holdings + reported totals | Comparison results and diagnostics |
| Generate reports | Holdings + comparison results | Admitted holdings panel and coverage reports |
| Triage | Excluded filings + source evidence | Saved explanations and review status |

## Step 3.1: Restore the configured inputs

Run from cs2b with the installed environment. The selected releases are 2026_04, 2026_05 and 2026_06. This configuration selects inputs explicitly; it does not monitor for new SEC releases.

source .venv/bin/activate

AWS_PROFILE=lantern dvc pull

dvc repro

dvc metrics show

The acquire stage verifies ZIP sizes and SHA-256 hashes in data/manifest.json. DVC also restores the four original HTML snapshots used by source evidence. Profile lantern must refer to an authorized AWS identity. The bucket stays private; the TA accepted demonstrating reproduction from the team’s configured environment.

## Step 3.2: Compare the correct values

Inputs: outputs/work/kept.parquet from cleaning, plus num.parquet, sub.parquet and canon.parquet from parsing. reconcile.py sums current-period holding fair values and compares them with the unique, finite, undimensioned USD InvestmentOwnedAtFairValue fact at the SUB period end. Missing or conflicting totals are not guessed or replaced with another tag.

Absolute gap = |holdings sum − filed total| / |filed total|. The tolerance is 0.01. A $15m filed total permits 15.15m; $15.5m fails. rec.parquet stores arithmetic and admission decisions; diag.parquet stores investigation clues.

## Step 3.3: Read the panel and coverage

report.py reads retained holdings, reconciliation, diagnostics, cleaning log and SUB, together with data/triage.csv. It writes outputs/panel/holdings.parquet for admitted filings only, plus reports/coverage.csv, coverage.json, coverage.md, triage.md and cleaning_log.csv. Each panel row retains release and source_rows. Annotated rows also retain source fact IDs, document hashes, URLs and precision.

Combined PR #42 snapshot (17ecff2, 2026-10-29, including PR #41): 101/177 attempted filings admitted (57.1%), 76 excluded, and $240,917,454,804 of $542,175,875,908 known filed dollars covered (44.4%). The panel has 34,670 holdings and 38,053 source-row references. Six additional SUB filings have no SOI rows; eight attempts lack a usable filed total. Unknown totals are not estimated as zero dollars.

## Step 3.4: Investigate exclusions and preserve evidence

Edit data/triage.csv, not generated triage.md. A note records accession, category, source evidence, a row example, fix or reason, review status and reviewed totals. Categories include totals_counted, cash_lines and restated_copies. Use other with an explicit unresolved cause when evidence is insufficient. A large gap alone does not prove duplication.

Recovered example: AGL (0001193125-26-214378) summed to $1,278,898,000 against $1,249,444,000 reported. The original filing identifies $29,454,000 as cash outside the investment total. A source-verified rule removes that row and the sum matches exactly.

Still excluded: Blackstone Private Credit Fund (0001803498-26-000031) sums to $88,167,227,000 against $80,469,381,000, a +9.566% gap. No supported correction is established. Missing-value contexts are clues, not proof of the cause. Keep the filing excluded. Its exclusion evidence is reviewed, while its underlying cause remains unresolved.

The source-evidence extension carries curated roles, instrument links and XBRL precision through parsing. It verifies snapshot fingerprints, source contexts and values before guarded cleaning. It recovered AGL, TriplePoint Private Venture, Chicago Atlantic and Prospect Floating Rate, moving admissions from 97 to 101. Three match exactly; Chicago differs by $287. These are generic evidence checks, not issuer-specific branches or target-gap matching. Unannotated future filings remain unchanged.

All 76 current exclusion decisions have reviewed dataset evidence (2026-10-30 audit). The underlying causes of 64 discrepancies remain unresolved under `other`; review completion does not mean those causes are known or the filings recovered. Complete review requires evidence, an explanation and current totals. A status label alone is insufficient. Historical notes for recovered filings remain saved; changed totals require re-review. Not every filing must pass, and unresolved drafts must not be marked reviewed simply to satisfy acceptance.

## Step 3.5: Validate and share the artifacts

python tests/run_tests.py

PYTHONPATH=src python -m lookthrough.check

python tools/baseline.py

python tools/rule_impact.py

Current validation: 57/57 tests and 10/10 structural checks pass. The 2026-10-29 snapshot previously passed 49 tests and caught 25 deliberate rule breaks; that mutation experiment was not rerun for this documentation/reporting patch. The provenance self-check samples 25 rows; the separate exclusion audit checked all 30,910 retained references for exclusions. Neither claims that all original filings were manually read.

After an intentional rule or evidence change, run dvc repro, refresh supplementary reports, review differences, then publish with AWS_PROFILE=lantern dvc push and commit the lockfile, code and small reports. PR #42’s snapshots and rebuilt artifacts are already uploaded; DVC confirmed cache and remote in sync. Computation runs locally; S3 stores artifacts.

## What broke and how we fixed it

The early baseline used starter rules. Integrating reviewed team rules established 90 admissions; source-supported summary and repeat fixes raised this to 94, 97 and then 101. We kept parsing, cleaning and orchestration separate, rejected ambiguous totals and preserved tranche/context guards. PR #41’s commitment rule removes 2,357 candidate rows without changing the final 101 admissions.

Four recoveries needed information absent from SOI labels. We added versioned classification and precision evidence instead of loosening matching. Prospect’s repeat is a narrative valuation disclosure, not a roll-forward. Partial missing fair values do not automatically exclude a filing; all-missing values cannot pass. Passing tests never meant that every real-data investigation was complete.

## Evidence and limitations

Code and results: PR #42. Repository evidence: src/lookthrough/reconcile.py, report.py, evidence.py and clean.py; data/source_evidence.json, source_filings.dvc and triage.csv; reports/coverage.json, rule_impact.csv and tests_that_fail.md; docs/cleaning_log.md, schema.md and ai_engineering_log_lokesh.md. The AI log and documentation refresh are included in PR #43.

The second-release and economics reports describe earlier experiments, not fresh measurements of the seven-rule panel. Principal currency remains a known limitation. No affiliation-reconciliation stretch result is claimed here.

Publication status: published to the shared codelab on 2026-10-29 through the authorized personal Gmail browser session. Verified replacement content, headings and preservation of neighboring sections. Google Docs showed Saved to Drive. Repository documentation changes are included in PR #43.

PR #43 refresh: the 20-holding spot check now covers the 101-filing panel (19 matches; one equity quantity stored as principal). The frozen reviewed sample is preserved separately from future deterministic draws. Principal currency and equity quantity remain limitations.


## Submission-readiness update — 2026-10-30

The local section is updated; this paragraph has not yet been republished to the shared Google Doc.
The panel remains 101 admitted / 177 attempted. All 76 exclusion decisions now
have reviewed dataset evidence and current totals: 8 missing required totals,
3 without recognized identifiers, 1 unfunded adjustment explanation, and 64
verified but unresolved discrepancies (`other`). The audit independently checks
raw NUM reference totals and 30,910 retained SOI references; it does not claim
that every original filing has been manually read or every cause determined.
See `reports/triage_review_audit.csv` and individual notes.

Recovered filings' 11 historical notes remain in `data/triage_recovered.csv`.
Teaching notebooks write only in the runner's scratch workspace. Regenerate
submission evidence with `dvc repro`. The optional affiliation stage and custom-tag
counterfactual audit are described in `reports/affiliation.md` and
`reports/custom_tag_recovery.md`. No new custom-tag admissions were established.
