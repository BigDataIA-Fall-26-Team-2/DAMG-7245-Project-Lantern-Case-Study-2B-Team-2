# AI Engineering Log — Sai Lokesh Reddy Nandavarapu

Part 3 reconciliation, coverage, triage and source-evidence follow-up.
Snapshot: 2026-10-29, PR #42, branch Lokesh-part3-triage-fixes, code commit 17ecff2.
This log records AI-assisted work; it is not a claim that every triage note has
received independent human review.

## Tools and responsibilities

Codex assisted with repository inspection, Python implementation, adversarial
tests, filing investigation, documentation and PR reviews. Terminal tools included
Python/pandas, Git/GitHub CLI, DVC and AWS access through the lantern profile.
The SEC source filings, SOI/NUM tables, configuration and existing team rules
were the evidence inputs. No AI model or RAG inference runs in the pipeline.
The specific model version is not recorded here.

Lokesh reviewed proposed changes and authorized implementation, commits and
publication in stages. Shravya owns the parsing foundation and DVC orchestration;
Dhruvi owns the original cleaning rules and rule-breaking framework; Guna owns
acquisition and spot checks. Part 3 builds on those contributions.

## What AI assisted with

- A configuration-driven contract for one or several releases, input fingerprint
  verification and reproducible baseline results.
- Safer reported-total selection, explicit missing/zero/conflicting-value
  handling, coverage denominators and source-row provenance checks.
- Admitted-only panel generation and consistent CSV/JSON/Markdown coverage.
- Persistent triage input in data/triage.csv, including completeness and stale
  total checks. Report generation does not overwrite investigation notes.
- Source inspection and draft explanations for excluded filings, followed by
  guarded summary and repeated-disclosure rules where evidence justified them.
- Six curated fact annotations across four original HTML snapshots, checked
  during parsing and carried into cleaning and panel provenance.
- Review feedback on teammate PRs and integration of PR #41's commitment rule.

## Decisions and corrections

| Finding or earlier mistake | Correction and boundary |
|---|---|
| Anonymous DVC access conflicted with a private bucket | Use authenticated AWS access, including local profile lantern. A local profile is configuration, not permission by itself. The TA's supplied chat accepts demonstrating the pull from our configured environment. No public bucket is required. |
| Baseline coordination accumulated cleaning logic | Keep rule behavior in cleaning functions and baseline code as orchestration. |
| Duplicate matching could remove a revolver as a term-loan copy | Review prompted debt-form, context and evidence checks and regression tests. Matching value or borrower name alone is insufficient. |
| Summary labels and classification prefixes inflated some totals | Add narrowly matched summary handling and preserve instrument/tranche distinctions. No company/adsh or target-gap exceptions in rule code. |
| Four recoveries needed information absent from SOI labels | Add versioned source roles, identities and precision; do not hardcode fund names or loosen numeric matching. |
| Prospect's repeat was described as a roll-forward | Original evidence showed a narrative valuation disclosure. Record narrative_repeat rather than invent opening-balance evidence. |
| A claim implied partial missing fair values always prevent admission | Corrected: all-missing holdings cannot pass, but partially missing values may coexist with a passing sum. Their presence alone does not prove a root cause. |
| Passing tests or integrating cleaning was treated as finishing triage | Corrected: code tests do not establish the cause of every real-data exclusion. Draft notes remain draft. |
| Removing rows can make totals match by accident | Require source evidence and unchanged retained amounts; an observed gap is not a row-deletion rule. |

## Source-evidence recoveries

The source-evidence extension alone moved admissions from 97 to 101. It removed
exactly four rows; the other 173 filing results and all retained holding values
were identical before integration of PR #41.

| Filing | Supported correction | Result |
|---|---|---|
| AGL, 0001193125-26-214378 | $29,454,000 cash-equivalent position outside investment total | $1,249,444,000, exact match |
| TriplePoint Private Venture, 0001792509-26-000017 | $9,078,000 cash-equivalent position outside investment total | $385,098,000, exact match |
| Chicago Atlantic, 0001193125-26-222738 | Unique roll-forward repeat with documented source precision | $363,967,000 vs $363,966,713; $287 gap |
| Prospect Floating Rate, 0001521945-26-000054 | Narrative repeat of the source-linked WatchGuard loan | $63,037,631, exact match |

Evidence: data/source_evidence.json, data/source_filings.dvc,
docs/cleaning_log.md and tests/test_lookthrough.py. Curated roles and identity
links are evidence inputs, not automatic semantics or human sign-off.

## Verification and final combined result

After integrating Dhruvi's merged PR #41 commitment rule:

- DVC pipeline rerun: 101/177 admitted (57.1%), 76 excluded.
- Known filed dollars: $240,917,454,804 / $542,175,875,908 (44.4%).
- Panel: 34,670 holdings, 38,053 source-row references and 3,972 non-debt rows.
- 49/49 tests pass. All 25 deliberately broken rule variants were caught.
  The mutation tool restored clean.py byte-identical and the suite passed again.
- Structural checks: 9/10 pass. The remaining failure is the incomplete or stale
  draft triage for 76 excluded filings. Sampled provenance check: 25 rows.
- DVC reported data/pipelines up to date, then cache and private remote in sync
  after the authorized uploads. Git work was published in PR #42.

Evidence: reports/coverage.json, reports/tests_that_fail.md,
reports/rule_impact.csv, dvc.lock and the recorded command outputs in this session.
The structural check is not an audit of every source holding.

## Remaining uncertainty and handoff

The 76 current exclusions do not all need to become admissions. Their explanations
need evidence review, with unresolved causes stated explicitly. For example,
Blackstone Private Credit Fund remains +9.566% above its reference; no supported
correction is established. Never mark it reviewed solely because a category
exists. Historical notes for recovered filings remain in the input CSV.

Future releases use the same code. Unknown patterns remain untouched/excluded
until justified evidence and regression tests support an extension. Principal
currency remains a known limitation. Earlier second-release and
economics reports are historical measurements, not new validation of this final
seven-rule run. The optional affiliation-reconciliation stretch goal is not
claimed as implemented by this work.

## Documentation publication

The Part 3 codelab section was published on 2026-10-29 through the authorized
personal Gmail browser session after the work-account connector returned 403.
Readback confirmed the five step headings, current results and draft-triage
limitations, with surrounding teammate sections preserved. README, schema and
this log were refreshed locally; these documentation changes are included in PR #43.

PR #43 refresh: the 20-holding spot check now covers the 101-filing panel (19 matches; one equity quantity stored as principal). The frozen reviewed sample is preserved separately from future deterministic draws. Principal currency and equity quantity remain limitations.

## PR #43 review follow-up (2026-10-30)

Codex found that equal-value sorting made the old seed-7 sample vary across
runtime environments. Replaced positional random draws with seeded SHA-256
ranking and explicit holding identity tie-breaks. Preserved Guna's 20 completed
reviews; new draws go to a separate file and are not represented as reviewed.
Added a regression check for shuffled input and equal fair values to the existing
test file. This branch passes 50/50 tests. Part 3's 49-test results above describe
the earlier PR #42 snapshot, not this follow-up.
