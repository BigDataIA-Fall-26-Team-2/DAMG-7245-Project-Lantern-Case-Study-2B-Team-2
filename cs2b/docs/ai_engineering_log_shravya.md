# AI Engineering Log — Shravya Ushake (Part 1 parsing and schema, Part 5 pipeline and economics, second-release stretch)

Branches `shravya/part1-parsing` (PR #2, merged), `shravya/part1-agreement` (PR #38), `shravya/part5-pipeline` (PR #40). Case Study 2B, release 2026q2 (2026_04, 2026_05, 2026_06; 183 filings, 177 with SOI rows).

## 1. Tools and tasks

| Tool / model | Used for |
|---|---|
| Claude (Anthropic, claude.ai chat with a code sandbox and web search) | Explaining the starter code, profiling the uploaded release ZIPs, proposing and writing code (`combine.py`, changes to `holdings.py`, the five stage scripts, `dvc.yaml`), drafting `docs/schema.md`, `reports/agreement.md`, `reports/economics.md`, `reports/second_release.md`, commit messages and PR descriptions, and looking up the SEC release list and an AWS instance price |
| Terminal, git, DVC, AWS CLI | I ran every command on my laptop: loading and checking data, running tests and the pipeline, committing, pushing, `dvc pull` / `dvc push`, and the fresh-clone rehearsal |
| EDGAR inline viewer | I opened the three agreement filings myself and checked each total on the printed schedule (screenshots kept) |
| Teammates | Guna (Part 0 data and manifest; Part 4 spot-check numbers used in economics), Lokesh (S3 bucket and access) |

## 2. What the AI contributed

- **Data profiling** of the real release: which SOI columns map to each field, fill rates and value ranges, and the discovery that April's fair values sit in a column (`Initial fair value of Investment`) the starter mapping missed.
- **Code:** `src/lookthrough/combine.py` (loads all monthly releases as one quarter, merges the TAG tables of every month, adds `release` and `subsidiary`); the `holdings.py` change that keeps `release` and adds `subsidiary` to the holding key; `scripts/acquire.py` (verify-only), `parse.py`, `clean.py`, `reconcile.py`, `report.py`; `dvc.yaml`.
- **Analysis code** run as one-off commands: conflict counts by field, the joint-venture investigation, the per-filing period split, the agreement totals, the unmapped-column decisions, the coverage comparison with 2026_08.
- **Drafts** of `docs/schema.md`, `reports/agreement.md`, `reports/economics.md`, `reports/second_release.md`, this log, commit messages, PR descriptions and team messages.

## 3. How it was verified

- **Every number re-run on my laptop.** The first schema draft used figures from the AI's sandbox; I re-ran each check on my own copy of the data before committing (for example April fair values: 0 of 4,378 rows with the starter mapping, 4,177 after the fix).
- **Data identity.** My local release matched Guna's manifest (all three SHA-256 hashes) and, once access worked, `dvc status` confirmed it matched `data/raw.dvc`.
- **Tests.** `python tests/run_tests.py` passed 17/17 after changing shared `holdings.py`.
- **Filings checked by eye.** For `agreement.md` I found each total in the filing: TCW Steel City $381,917,205; Oaktree 2,766,367 thousand; TCW Direct Lending VII $645,193,114 and its footnote total $107,862,000, which equals the remaining gap exactly.
- **Pipeline equal to the team's version.** After running the five stages, `git diff` on coverage.csv, coverage.json, coverage.md, triage.md and cleaning_log.csv was empty, and the panel matched row for row (34,755 rows, 22 columns, same fair-value total). The byte difference DVC reported was parquet metadata only, checked by comparing contents.
- **Pipeline behaviour.** A second `dvc repro` skipped every stage; forced reruns left `dvc.lock` unchanged (deterministic outputs).
- **Fresh-clone rehearsal.** New clone → `dvc pull` → `dvc repro` → `dvc repro --force`: identical outputs, `git status` clean, self-check 9/10 (the failing check is triage, Part 3).

## 4. What changed and why (decisions, including the AI's own mistakes)

| Change or decision | Why |
|---|---|
| Built the combine step in a new `combine.py` instead of editing `load.py` | Avoid conflicts with starter code; one place for multi-release logic. |
| Merged the TAG tables of all months before mapping | April's own TAG table lacks the us-gaap/2026 label, so per-month mapping gave April no fair values. Still mapping by tag, as the spec requires. |
| Added `subsidiary` (Nonconsolidated Subsidiary Axis) to the holding key | 24 filings list joint-venture portfolios; without it, two JVs' positions in the same loan were merged and one value discarded. Fair-value conflicts fell from 200 to 2. |
| Did not trust the first reading of the JV rows | The AI suggested they were JV portfolios; I confirmed it in Oaktree's filing (its fair-value note counts its stake in the JVs, not their loans). |
| Treated the BOCSO conflict as unverified | The AI noted sister funds report identical figures and may describe BOCSO as a whole; this is stated as unverified in `schema.md`, not as fact. |
| Moved Guna's download script to `tools/` and made `scripts/acquire.py` verify-only | The download script wrote into DVC-owned `data/raw` and rewrote `manifest.json` with today's date on every run, which would break reproducibility. |
| Split `run_baseline` into five stages without changing any logic | Each stage calls the same functions in the same order, so results stay identical and `dvc repro` reruns only what changed. |
| Retired `outputs/panel.dvc` | The pipeline now produces the panel; a path cannot be owned by both a `.dvc` file and a stage. |
| Fixed DVC access with a local profile and `allow_anonymous_login false` in `.dvc/config.local` | The AI first suggested making the bucket public; testing showed I already had the right AWS profile, but `allow_anonymous_login = true` made DVC skip it. |
| Rejected two broken AI commands | Using `/dev/null` as an AWS config file failed; a lookup on a NaN key crashed. Both replaced with working versions. |
| Rewrote `second_release.md` without a nested code block | The chat broke the AI's nested code box and turned quotes curly, which would have corrupted the `sed` command. |

## 5. Failures, limits and open uncertainty

- **Graders cannot pull without a login** (found in the rehearsal: "Unable to locate credentials"). Needs a public-read bucket or another arrangement before submission; raised with the team.
- **4,032 current rows** have an issuer name but no identifier and are dropped; their effect on coverage was not measured.
- **Economics assumptions** (1 analyst hour per filing, $75/hour, cloud run about 3× slower than my laptop) are stated assumptions, not measurements.
- **Second release:** 2026_08 is not in the team's DVC remote; BDCs were matched across releases by name.
- **"Initial fair value of Investment"** as the label of a standard tag was not checked against the official us-gaap 2026 taxonomy.

## 6. Confidence and responsibility

I am confident in the parsing, the combine step and the pipeline: every figure in my reports was reproduced on my laptop, the agreement totals were checked in the filings themselves, and the staged pipeline reproduces the team's outputs exactly. I am less confident in the economics assumptions, which are stated as such. I can explain, modify, test and defend every file listed above, and I take responsibility for them.