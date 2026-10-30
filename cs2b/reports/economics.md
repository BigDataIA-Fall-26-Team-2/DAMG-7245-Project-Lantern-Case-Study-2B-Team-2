# Unit economics (Part 5)

Release: 2026q2 (monthly SEC BDC data sets 2026_04, 2026_05, 2026_06), 183 filings in SUB, 177 with SOI rows. Pipeline: `dvc repro` (acquire → parse → clean → reconcile → report) with the final seven cleaning rules. "Completed task" = one filing reconciled and admitted to the panel.

## Five-line table

| Line | Value | How it was measured or assumed |
|---|---|---|
| Cost per completed task | ≈ $0 on a laptop; ≈ $0.000008 per admitted filing on cloud | Laptop: no marginal cost. Cloud equivalent: AWS m7i-flex.large at $0.0958/hour on-demand (us-east-1). Assumes the full run takes ~30 s there (about 3× our laptop time, a stated assumption: fewer and slower cores). 30 s × $0.0958/3600 s ≈ $0.0008 per run; ÷ 183 filings ≈ $0.0000044 per filing processed; ÷ 101 admitted ≈ $0.0000079 per completed task. No model or API cost: the pipeline uses no AI model. |
| Latency | 9.7 s for the whole release; 0.053 s per filing (0.096 s per admitted filing) | Measured with `/usr/bin/time -p dvc repro --force -s <stage>` on an Apple M3 Pro, 18 GB RAM, on the final pipeline: acquire 0.38 s, parse 5.23 s, clean 2.34 s, reconcile 1.20 s, report 0.55 s. Includes about 0.5 s of DVC overhead per stage. Excludes the one-time `dvc pull` (~664 MB of raw data). |
| Human time replaced | 50.5 / 101 / 202 analyst hours per quarter (×0.5 / ×1 / ×2) | Assumption: reconciling one BDC filing by hand (rebuild the schedule in a spreadsheet, remove totals and duplicate sections, match the filed total) takes 1 hour (×1). Applied to the 101 admitted filings only, since excluded filings still need a human. At an assumed $75/hour loaded analyst cost: $3,788 / $7,575 / $15,150 per quarter. |
| Quality | Coverage: 101 of 177 filings (57.1%), $240.9B of $542.2B filed fair value (44.4%). Spot-check agreement on the final panel: 19 of 20 sampled holdings (95%) across 10 filings match the filing on fair value and principal; the 20th matches on fair value, but its principal field holds a unit count for an equity holding (Great Elm Capital Corp., SOI rows 50077;50078). | `dvc metrics show` (reports/coverage.json); spot checks in reports/spot_check.csv and reports/dependency_check.md (Part 4). Every admitted filing matches its filed total within 1% (`reconcile.tolerance`). 6 filings have no SOI rows; 8 have no usable filed total. The commitment-line exception found in the first spot-check sample is now removed by `rule_commitment_rows`. |
| Scale | ~80 s of compute and well under $0.01 of cloud cost for every release since Q4 2022 | The SEC lists 22 BDC releases from 2022 Q4 to 2026 March (~298 MB of ZIPs); with our 3 months, ~340 MB, about 8× our quarter's 42 MB. Assuming runtime scales with data size: 8 × 9.7 s ≈ 78 s on the laptop, ~4 minutes on the cloud instance (≈ $0.006). Downloads at the SEC's request limits add a few minutes. Older releases are smaller, so this is an upper estimate. Checked on one more release: the pipeline ran unchanged on 2026_08 (see reports/second_release.md, which uses the earlier five-rule baseline). |

## Build versus buy

The starter kit saved most of the plumbing: typed loaders for SUB, TAG, NUM and SOI, tag-based column mapping, period splitting, row coalescing, the reconciliation and coverage functions, the self-check and the fixture. No commercial product sells a BDC look-through panel that is reconciled filing by filing and traceable to SOI rows, and open-source tools (such as EdgarTools) parse the schedules but do not reconcile them or explain exclusions. What we still had to build is the part that makes the numbers trustworthy for this release: combining three monthly files into one quarter (including a fix for April's fair-value column, which the starter mapping missed entirely), keeping joint-venture portfolios apart from a BDC's own holdings, seven cleaning rules motivated by artifacts in our filings, triage of every excluded filing, a spot-check of the dependency, and a reproducible five-stage DVC pipeline. The compute cost is negligible; the real cost is the analyst time to investigate artifacts, which this pipeline turns into documented, re-runnable rules.

## Sources
- SEC BDC data sets (release list and sizes): https://www.sec.gov/data-research/bdc-data-sets
- AWS m7i-flex.large on-demand price, us-east-1: https://www.devzero.io/instances/aws/m7i-flex.large
- Our measurements: `dvc repro --force -s <stage>` timings and `dvc metrics show`, run on 2026-10-30 on the final pipeline.
- Spot-check agreement: reports/spot_check.csv and reports/dependency_check.md (Part 4).
