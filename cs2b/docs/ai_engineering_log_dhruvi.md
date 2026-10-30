# AI Engineering Log — Dhruvi Mehta (Part 2 cleaning, Part 5 tests that fail)

Branch `dhruvi/part2-cleaning`, PR #3. Case Study 2B, release 2026q2 (177 filings).

## 1. Tools and tasks

| Tool / model | Used for |
|---|---|
| Claude (Anthropic, claude.ai chat with a code sandbox) | Exploring the real SOI/NUM data, proposing and writing cleaning rules, tests, measurement tools (`tools/rule_impact.py`, `tools/break_rules.py`, `tools/verify_examples.py`) and the write-ups in `docs/cleaning_log.md` and `reports/tests_that_fail.md` |
| Terminal, git, GitHub CLI (`gh`), DVC | I ran every command on my laptop: applying changes, running tests and tools, committing, pushing, and PR comments and review replies |
| Teammate review (Lokesh, PR #3) | Independent challenge of the rules on hand-made inputs |

## 2. What the AI contributed

- **Investigation of all 9 artifacts** on the real quarter: profiling failing filings, finding the rows behind each overcount or undercount, and measuring candidate rules.
- **Code in `src/lookthrough/clean.py`:** `rule_jv_portfolio`, `rule_issuer_subtotals`, `rule_rollforward_copies`, the filer-aware `rule_cash`, the false-positive fix to the starter `rule_totals`, `instrument_kind`, `flag_debt`, the shared `RULES` list, and the change to `apply_rules` so each rule sees only surviving rows.
- **Tests:** one per rule, the regression tests from both reviews, and the debt-flag test.
- **Tools:** `rule_impact.py` (coverage with and without each rule), `break_rules.py` (Part 5), `verify_examples.py` (opens every cleaning-log example in the raw `soi.tsv`).
- **Drafts** of `docs/cleaning_log.md`, `reports/tests_that_fail.md`, commit messages, PR comments and review replies.

## 3. How it was verified

- **Tests on every change.** `python tests/run_tests.py` ran before each commit (17 → 41 tests in the team suite, all passing).
- **Real-data measurement for every rule.** Each rule was run on the full 2026q2 quarter with and without it, recording filings admitted, filings harmed and filings pushed further from their total (`reports/rule_impact.csv`). A rule was kept only if it harmed no admitted filing, or the one exception was explained.
- **Examples checked against the source.** Every cited example names its filing (adsh), month file and SOI row. `tools/verify_examples.py` opens each one in the raw file (`reports/cleaning_log_check.md`).
- **Tests proven able to fail.** `tools/break_rules.py` removes or breaks each rule 20 ways and confirms a test fails each time, then restores `clean.py` byte-identical.
- **Independent review, twice.** Lokesh reproduced two bugs on hand-made inputs. Both were fixed, and each fix has a regression test that fails on the pre-review code (23 of 28 pass there) and passes after. His second review of 6fd1844 showed the roll-forward fix was still too coarse (a revolver deleted as a copy of a same-value term loan); that fix also has regression tests that fail on 6fd1844.
- **Before/after diff of the review fixes.** Row by row: no new rows dropped, 177 rows ($912.5M) now kept, still 90 of 177 filings and 43.5% of dollars, no admitted filing lost.

## 4. What changed and why (decisions, including the AI's own mistakes)

| Change | Why |
|---|---|
| Fixed the starter `rule_totals` | It deleted real companies named "Total Expert, Inc.", "Total Access Elevator, LLC" and others. TriplePoint Venture Growth went from −2.85% to 0.00%. |
| Let TriplePoint Private Venture Credit fail rather than keep its admission | It matched only because the totals bug deleted a real $7.5M loan, which hid a separate ~$9.1M overcount. Being right for the wrong reason is not evidence. |
| Narrowed `rule_issuer_subtotals` twice | The first version had 5 false positives (sibling tranches, loose tolerance). The review then showed an unrestricted name prefix ("ABC" / "ABCD LLC"). Now it requires a word boundary, ignores company-suffix and tranche differences, and keeps parents that name an instrument. |
| Made `rule_rollforward_copies` instrument-aware and one-to-one | The review showed a preferred-equity holding deleted as a "copy" of a same-value loan. Debt now never matches equity, and each original vouches for one copy only. |
| Required roll-forward evidence, and matching debt forms, in `rule_rollforward_copies` | Second review: "debt vs equity" still let a revolver be deleted as a copy of a same-value term loan. A copy now needs the roll-forward's opening balance on its identifier (318 of the 324 real copies have it), and a revolver never matches a term loan. Only Prospect changes (+3.3% → +4.4%, not admitted either way); still 90 of 177. |
| Added `rule_commitment_rows` from Guna's Part 4 spot check | Guna found a sampled "holding" that was an unfunded-commitment table row. Measured first: 2,357 such rows in 11 filings, no admission changes, 4 admitted filings move closer to their totals and none further. Kept narrow (needs both "Commitment Type" and "Commitment Expiration Date" and no cost/principal), unlike the earlier drop-all-negatives test that harmed 4 filings. |
| Changed `apply_rules` so rules see only surviving rows | The review showed a JV loan already dropped could still be used as evidence by a later rule. |
| Kept unfunded commitments (negative values) | Dropping them made 4 admitted filings fail. BDCs net them into the reported total. |
| Did not add a custom-tag recovery rule (stretch) | Recovering the custom fair-value facts double counted (TCW Direct Lending VII: +16.7% → +112%), including when tried before cleaning. Documented as an evidenced negative result. |
| Strengthened the subtotal test | The first `break_rules.py` run showed a 5% tolerance passed every test. The test now pins the 0.2% tolerance from both sides. |
| Flagged equity and warrants with `is_debt` instead of only keeping them | Required by the handout. 7,858 holdings ($51.7bn) are flagged, not dropped. |

## 5. Failures, limitations and uncertainty

- **AI mistakes caught during the work:**
  - a duplicated-sections bug in the cleaning log
  - a 1-based vs 0-based SOI row mix-up in one FS KKR citation (row numbers are 0-based `soi_row`; file line = row + 2)
  - an early claim that Part 2 was "nearly done" while the pipeline still used only the starter rules, `is_debt` was unused, and the log examples were unverified. I caught that against the handout checklist.
- **AI bugs a teammate caught:** both first-review findings (P1, P2) and the second-review finding (revolver vs term loan) were real bugs that the AI-written tests had missed. The first P1 fix was itself too coarse, which shows a fix needs its own adversarial test, not only the reviewer's exact example.
- **Known limitations** (`reports/tests_that_fail.md`):
  - `rule_cash` matches the words "money market" anywhere in a name.
  - The subtotal and roll-forward rules depend on identifier text.
  - Lord Abbett S is short by exactly its JV value, which is filed under a different tag. No rule recovers it.
  - Custom-axis filings (Partners Group, SuRo) cannot be cleaned and go to triage.
- **The cautious review fixes cost something:** 7 filings that were not admitted move further from their totals (e.g. Rand +9% → +33%). Those are passed to triage rather than guessed.
- **Some evidence was generated in the AI's sandbox** from the same release files. I reran the key outputs locally: tests, `rule_impact.py`, `verify_examples.py`, `break_rules.py`.

## 6. Confidence and responsibility

**Confidence:**
- **High** that each rule removes only what its write-up says. This is backed by real-data before/after counts, verified examples, regression tests, and 20 of 20 deliberate breaks caught.
- **Moderate** on edge cases outside 2026q2, because the rules rely on identifier wording.

**Responsibility statement:** I ran, reviewed and committed every change in PR #3. I can explain what each rule removes and why, how each test fails when its rule is broken, and why the stretch goal was documented rather than forced, and I am able to modify and defend this work.
