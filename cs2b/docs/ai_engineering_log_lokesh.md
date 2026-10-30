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


## Submission-readiness audit — 2026-10-30

User authorized priority fixes before freeze. Independently checked raw NUM filters
for eight `no_filed_total` cases and current canonical identifier counts for three
`no_identified_holdings` cases. These 11 notes now describe the narrow verified
exclusion mechanism, carry current reviewed totals, and are marked reviewed.
This was an AI-assisted dataset/code audit, not a claim that a teammate manually
reviewed all original filings. In particular, an absent qualifying NUM fact does
not mean the human-readable filing has no total. The other 65 notes remain draft.
Archived 11 historical notes for filings now admitted rather than deleting evidence.

Protected writing notebooks with a scratch-workspace guard and made the runner
copy the project before execution. Scratch configuration intentionally uses the
single teaching release; submission configuration remains multi-release. Shared
one provenance-based sampler between app and CLI, including zero-count behavior;
preserved frozen hand-check CSVs. Added `python-multipart` to requirements and
removed duplicate requests entry. Report wording now says complete only when
all current evidence is reviewed; real results correctly retain the warning.
Added a clear expired-run message instead of redesigning shared app state.

AWS inventory was read using `lantern`: m7i-flex.large, 40 GiB gp3, one Elastic IP,
and 71 current objects / 755,618,206 bytes in cs2b. The public AWS catalog confirmed
$0.09576/hour. Economics now budgets about $76.77/month always-on and explicitly
labels runtime/human-effort scenarios as assumptions. IAM denied authenticated
pricing and CloudWatch queries; no permissions were changed and no utilization
measurement is invented. Broader app authentication, durable multi-user storage,
and remaining triage investigation are outside this priority patch.

Validation: 55 focused tests; app startup/OpenAPI/upload registration; app/CLI
sample equality on the real panel; direct notebook write guards; isolated notebook
execution; seven cleaning examples traced. DVC outputs and lockfile regenerated.
The structural check is 9/10, with exactly 65 incomplete notes. No claim of 10/10
or final triage completion is made. Final tag must be `cs2b-submission` after merge;
the older `Submission` tag and deployed code have not been changed by this audit.


## Completed exclusion-decision review and stretch audit — 2026-10-30

After the user authorized completing the reviews and pushing a PR, integrated
main through 884a333 (including Guna's issue draft and Dhruvi's cleaning note).
Preserved the resource-based economics and included Shravya's reported 9.7-second
laptop timing with attribution; it is not a measured EC2 timing.

Independently audited all 76 current exclusions against raw tables: checked
30,910 retained SOI references, matching filing/date, unchanged retained amounts,
missing mapped values, sums and raw current undimensioned USD NUM references.
FS KKR's three negative type-level adjustments exactly offset its gap. Reviewed
all exclusion decisions and bound notes to current totals. For 64 `other` cases,
the notes explicitly say the underlying cause remains unresolved: source amount
traceability and exclusion correctness are established, not completeness of the
source schedule or freedom from repeated disclosures. No claim of 64 recovered
filings or manual review of every human-readable original is made. The user will
review these explanations in the PR. The checker was not weakened.

Added optional affiliation reconciliation using explicit standard SOI enumeration
members and current NUM category totals. Unknown/custom/conflicting membership,
missing values and conflicting totals cannot pass. The feature leaves the primary
panel unchanged. Added focused regression tests for these guards.

Custom-tag screen found 34 exact missing-value candidates in two TCW filings.
A counterfactual rerun through all seven rules recovered zero filings and worsened
both gaps. Existing source investigation identifies roll-forward balances. Kept
these out of production and documented candidate rows and before/after gaps;
custom-tag stretch completion is not claimed. This limitation is evidence-based,
not bypassed for bonus credit. No external issue, tag change, or EC2 deployment
was performed.

Final validation for this follow-up: 57/57 tests and 10/10 self-checks pass;
`dvc repro`, `dvc push`, and `dvc status` complete with the cache/remote and
pipeline up to date. Latest main reserialized all eight work Parquet tables;
comparison with its S3 objects confirms identical values, dtypes, and indexes.
The audited local serialization remains recorded in this branch's lockfile.
Affiliation output: 267 reported categories across 134 filings, one fully
classified category matches, 266 remain explicitly incomplete. The additional
stage is outside the teammate's earlier 9.7-second timing. No fresh-clone or EC2
validation is claimed; the user will perform those after merging.


## 2026-10-30 — Final submission review fixes

On `Lokesh-final-submission-fixes`, aligned TCW's reviewed exclusion with
original filing footnote 4: 12 valued non-controlled-affiliate rows total
$107,862,000 and repeat the schedule disclosure. The additional 18 rows have
missing fair values; they are not asserted to be 18 verified duplicate holdings.
TCW remains excluded, with category `restated_copies`; 63 exclusions remain
`other` with unresolved causes. No admission or cleaning rule was changed.
Source: https://www.sec.gov/Archives/edgar/data/1715933/000119312526141887/ck0001715933-20251231.htm

Shared upload/fetch/delete/refresh API operations now require an operator key
and are disabled when no key is configured. Removed these controls from the
public UI. Suppressed debt share because equity quantities can populate principal;
the optional debt filter is explicitly heuristic. Added access-control regression
coverage in the existing test file and its httpx dependency.

Updated README, schema, app documentation, codelab notes and economics. Economics
separates measured laptop timing, assumed human effort and estimated historical
runtime/cost. The historical estimate is 115 seconds on the laptop, not the
earlier 80-second estimate based on a smaller release inventory.

Validation: 58/58 tests and 10/10 self-checks pass. Regenerated report outputs
and dvc.lock; panel hashes and admissions remain unchanged (101/177 admitted,
76 excluded). Video remains pending. No final retag, commit, push or deployment
is claimed for this patch; final submission must include the video and be
validated after merge before moving `cs2b-submission`.
