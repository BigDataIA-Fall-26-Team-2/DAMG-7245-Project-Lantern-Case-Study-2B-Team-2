# Second release (stretch goal)

We ran the pipeline **unchanged** on a second release and compared coverage with our main release.

- **Main release:** 2026q2 (monthly SEC BDC data sets 2026_04, 2026_05, 2026_06; mostly first-quarter 2026 10-Qs).
- **Second release:** 2026_08 (second-quarter 2026 10-Qs, with comparative schedules at 31 December 2025).
- **What changed:** only `params.yaml` (`release: "2026_08"`, `releases: ["2026_08"]`). No code, rules or tolerance changed.

## How it was run (reproducible)

In a fresh clone of the Part 5 branch, run these three commands from `cs2b/`:

1. Edit `params.yaml`: set `release: "2026_08"` and `releases: ["2026_08"]`.
2. `python tools/download_release.py` downloads `2026_08_bdc.zip` (75,864,269 bytes, SHA-256 417e3f84…) and writes the manifest.
3. `dvc repro`

The run happened in a scratch copy, so the team's panel and reports were not overwritten. The 2026_08 coverage files are saved in `reports/second_release_2026_08/`.

## Coverage

| | 2026q2 (main) | 2026_08 (second) |
|---|---|---|
| Filings in SUB | 183 | 174 |
| Filings attempted (with SOI rows) | 177 | 169 |
| Filings without SOI rows | 6 | 5 |
| Filings without a usable filed total | 8 | 7 |
| Current holdings (before cleaning) | 64,762 | 64,207 |
| Holdings dropped by cleaning | 1,531 | 1,672 |
| **Filings admitted** | **90 (50.8%)** | **89 (52.7%)** |
| Filed fair value attempted | $542.2B | $510.7B |
| **Filed fair value admitted** | **$235.9B (43.5%)** | **$206.8B (40.5%)** |

Filing coverage is almost the same (+1.9 points) and dollar coverage slightly lower (−3.0 points), so the five cleaning rules generalise to a quarter they were not built on.

## BDC by BDC

Matching BDCs by name: 166 appear in both releases, 11 only in 2026q2 and 5 only in 2026_08. **75 BDCs are admitted in both.**

Largest BDCs admitted in 2026q2 but not in 2026_08 (gap in 2026_08):

| BDC | Filed FV, 2026q2 | Gap, 2026_08 |
|---|---|---|
| Golub Capital BDC | $8.32B | +1.69% |
| Blue Owl Technology Income Corp. | $5.22B | +25.79% |
| TPG Twin Brook Capital Income Fund | $4.48B | +2.04% |
| New Mountain Finance Corp | $2.31B | +14.19% |
| Kayne Anderson BDC | $2.21B | −1.69% |
| T Series BDC | $2.15B | +2.01% |
| Overland Advantage | $1.52B | −6.63% |
| TCW Direct Lending VIII | $1.31B | +11.04% |

Largest BDCs admitted in 2026_08 but not in 2026q2 (gap in 2026q2):

| BDC | Filed FV, 2026_08 | Gap, 2026q2 |
|---|---|---|
| Goldman Sachs Private Credit Corp. | $18.19B | −6.92% |
| Jefferies Credit Partners BDC | $1.91B | −1.03% |
| Goldman Sachs Private Middle Market Credit II | $1.37B | +4.08% |
| Runway Growth Finance Corp. | $1.19B | +1.47% |
| Gladstone Capital Corp | $0.95B | −5.84% |
| Commonwealth Credit Partners BDC I | $0.62B | +1.26% |
| Senior Credit Investments | $0.60B | −1.11% |
| Star Mountain Lower Middle-Market Capital Corp | $0.41B | +300.00% |

## What this shows

- **Half of the switches are near-misses at the 1% tolerance.** 4 of the 8 largest losses (Golub, TPG Twin Brook, Kayne Anderson, T Series) and 4 of the 8 largest gains (Jefferies, Runway, Commonwealth, Senior Credit) have gaps between 1% and 2.1% in the other release. Coverage near the boundary moves from quarter to quarter without any change in the rules.
- **The larger gaps point to artifacts the rules do not yet catch in 2026_08**: Blue Owl Technology Income (+25.8%), New Mountain Finance (+14.2%, a joint-venture filer in 2026q2), TCW Direct Lending VIII (+11.0%) and Overland Advantage (−6.6%). We did not investigate these; they are the first places to look if the rules are extended to 2026_08.
- **Star Mountain's +300% in 2026q2** is far larger than any cleaning artifact and is more likely a units or scale problem in that filing's data; also not investigated.
- **Triage was not done for 2026_08.** All excluded 2026_08 filings show the placeholder `to_triage`, as expected: triage is a human review of our main release only.

## Limits

- 2026_08 is not tracked in the team's DVC remote. To reproduce, follow the three steps above in a fresh clone.
- BDCs were matched by name; a renamed fund would appear as two different BDCs.