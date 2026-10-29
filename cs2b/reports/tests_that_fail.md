# Tests that fail

A test is evidence only if it can fail. For every cleaning rule we broke the rule in `src/lookthrough/clean.py`, ran `python tests/run_tests.py`, recorded the failures, restored the file and re-ran the suite.

Each rule is broken two ways: **removed** (the rule drops nothing) and **broken** (one realistic bug, usually a mistake we made and fixed while writing the rule). The run is automated and repeatable:

```
python tools/break_rules.py
```

- Suite before breaking: **41/41 tests pass**
- Breaks applied: **20**; caught by at least one failing test: **20 of 20**
- `clean.py` restored byte-identical after the run: **True**
- Suite after restoring: **41/41 tests pass**

## Summary

| Rule | Break | Result | Failing test(s) |
|---|---|---|---|
| `rule_totals` | removed: the rule drops nothing | 33/41 tests pass | `test_baseline_reconciliation_counts_every_filing`, `test_checker_catches_a_silently_dropped_filing`, `test_checker_passes_baseline_and_catches_tampering`, `test_checker_rejects_missing_totals_and_gap_tampering`, `test_checker_uses_release_and_row_together`, `test_reports_preserve_triage_and_flag_changed_totals`, `test_total_rule_spares_companies_named_total`, `test_total_rule_spares_ordinary_names` |
| `rule_totals` | broken: the company-suffix / maturity-date guard is removed, so borrowers named "Total ..." are dropped again (the Total Expert bug) | 40/41 tests pass | `test_total_rule_spares_companies_named_total` |
| `rule_cash` | removed: the rule drops nothing | 34/41 tests pass | `test_baseline_reconciliation_counts_every_filing`, `test_cash_rule_keeps_money_market_labelled_short_term_investment`, `test_checker_catches_a_silently_dropped_filing`, `test_checker_passes_baseline_and_catches_tampering`, `test_checker_rejects_missing_totals_and_gap_tampering`, `test_checker_uses_release_and_row_together`, `test_reports_preserve_triage_and_flag_changed_totals` |
| `rule_cash` | broken: the short-term-investment exception is removed, so the filer-aware rule falls back to the starter behaviour (Palmer Square, Great Elm fail again) | 40/41 tests pass | `test_cash_rule_keeps_money_market_labelled_short_term_investment` |
| `rule_commitment_rows` | removed: the rule drops nothing | 40/41 tests pass | `test_commitment_rule_drops_only_unfunded_commitment_rows` |
| `rule_commitment_rows` | broken: the no-cost/no-principal guard is removed, so a row carrying principal is dropped as a commitment | 40/41 tests pass | `test_commitment_rule_drops_only_unfunded_commitment_rows` |
| `rule_jv_portfolio` | removed: the rule drops nothing | 39/41 tests pass | `test_jv_portfolio_rule_drops_only_jv_rows`, `test_rollforward_rule_ignores_a_counterpart_already_dropped_as_jv` |
| `rule_jv_portfolio` | broken: the rule tests the wrong column and drops every identified holding, not only rows on the Nonconsolidated Subsidiary Axis | 35/41 tests pass | `test_checker_uses_release_and_row_together`, `test_combined_baseline_uses_one_copy_of_repeated_filings`, `test_jv_portfolio_rule_drops_only_jv_rows`, `test_reports_preserve_triage_and_flag_changed_totals`, `test_reports_reject_panel_mismatch_or_missing_provenance`, `test_rollforward_rule_ignores_a_counterpart_already_dropped_as_jv` |
| `rule_issuer_subtotals` | removed: the rule drops nothing | 40/41 tests pass | `test_issuer_subtotal_rule_drops_only_true_subtotals` |
| `rule_issuer_subtotals` | broken: the sibling-tranche check is removed, so "Revolver One" / "Warrant 2" count as children of a parent line (the first-version bug) | 40/41 tests pass | `test_issuer_subtotal_rule_drops_only_true_subtotals` |
| `rule_issuer_subtotals` | broken: the sum tolerance is loosened from 0.2% to 5%, so a parent that only roughly equals its children is dropped | 40/41 tests pass | `test_issuer_subtotal_rule_drops_only_true_subtotals` |
| `rule_issuer_subtotals` | broken: the word-boundary check is removed, so "ABC" is treated as the parent of "ABCD LLC" (review finding P2) | 40/41 tests pass | `test_issuer_subtotal_rule_needs_a_real_name_boundary` |
| `rule_issuer_subtotals` | broken: the company-suffix check is removed, so "XYZ" is treated as the parent of "XYZ, LLC" (review finding P2) | 40/41 tests pass | `test_issuer_subtotal_rule_needs_a_real_name_boundary` |
| `rule_issuer_subtotals` | broken: a parent that names an instrument may be dropped, so one loan is treated as the subtotal of another (review finding P2) | 40/41 tests pass | `test_issuer_subtotal_rule_keeps_a_parent_that_names_an_instrument` |
| `rule_rollforward_copies` | removed: the rule drops nothing | 38/41 tests pass | `test_rollforward_copy_rule_drops_only_bare_twins`, `test_rollforward_evidence_is_an_opening_value_without_cost_or_principal`, `test_rollforward_rule_lets_one_holding_vouch_for_one_copy` |
| `rule_rollforward_copies` | broken: the instrument check is removed, so preferred equity is dropped as a copy of a loan with the same value (review finding P1) | 40/41 tests pass | `test_rollforward_rule_keeps_a_distinct_instrument_with_the_same_value` |
| `rule_rollforward_copies` | broken: the debt-form check is removed, so a revolver is dropped as a copy of a term loan with the same value (second review finding) | 40/41 tests pass | `test_rollforward_rule_keeps_a_revolver_that_matches_a_term_loan_by_value` |
| `rule_rollforward_copies` | broken: the roll-forward evidence requirement is removed, so any bare row is a candidate copy (second review finding) | 40/41 tests pass | `test_rollforward_evidence_is_an_opening_value_without_cost_or_principal` |
| `rule_rollforward_copies` | broken: a schedule holding may vouch for any number of copies, so two bare rows are dropped against one counterpart (review finding P1) | 40/41 tests pass | `test_rollforward_rule_lets_one_holding_vouch_for_one_copy` |
| `apply_rules` | broken: every rule sees the original frame, so a JV loan already dropped still serves as the counterpart for a BDC holding (review finding P1) | 40/41 tests pass | `test_rollforward_rule_ignores_a_counterpart_already_dropped_as_jv` |

## Each break

### 1. `rule_totals`, removed

**Break:** the rule drops nothing.

```diff
- return (_matches(h, TOTAL) & ~_matches(h, NOT_A_TOTAL),
+ return (pd.Series(False, index=h.index),
```

**Result:** 33/41 tests pass. Failing: `test_baseline_reconciliation_counts_every_filing`, `test_checker_catches_a_silently_dropped_filing`, `test_checker_passes_baseline_and_catches_tampering`, `test_checker_rejects_missing_totals_and_gap_tampering`, `test_checker_uses_release_and_row_together`, `test_reports_preserve_triage_and_flag_changed_totals`, `test_total_rule_spares_companies_named_total`, `test_total_rule_spares_ordinary_names`.

```
AssertionError
AssertionError: [False, False, False, False, False]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 2. `rule_totals`, broken

**Break:** the company-suffix / maturity-date guard is removed, so borrowers named "Total ..." are dropped again (the Total Expert bug).

```diff
- _matches(h, TOTAL) & ~_matches(h, NOT_A_TOTAL)
+ _matches(h, TOTAL)
```

**Result:** 40/41 tests pass. Failing: `test_total_rule_spares_companies_named_total`.

```
AssertionError: [True, True, True, True, True]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 3. `rule_cash`, removed

**Break:** the rule drops nothing.

```diff
- return (_matches(h, CASH) & ~_matches(h, SHORT_TERM_INV),
+ return (pd.Series(False, index=h.index),
```

**Result:** 34/41 tests pass. Failing: `test_baseline_reconciliation_counts_every_filing`, `test_cash_rule_keeps_money_market_labelled_short_term_investment`, `test_checker_catches_a_silently_dropped_filing`, `test_checker_passes_baseline_and_catches_tampering`, `test_checker_rejects_missing_totals_and_gap_tampering`, `test_checker_uses_release_and_row_together`, `test_reports_preserve_triage_and_flag_changed_totals`.

```
AssertionError
AssertionError: [False, False]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 4. `rule_cash`, broken

**Break:** the short-term-investment exception is removed, so the filer-aware rule falls back to the starter behaviour (Palmer Square, Great Elm fail again).

```diff
- _matches(h, CASH) & ~_matches(h, SHORT_TERM_INV)
+ _matches(h, CASH)
```

**Result:** 40/41 tests pass. Failing: `test_cash_rule_keeps_money_market_labelled_short_term_investment`.

```
AssertionError: [True, True]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 5. `rule_commitment_rows`, removed

**Break:** the rule drops nothing.

```diff
- return t.str.contains(COMMITMENT_ROW, regex=True) & ~terms, why
+ return pd.Series(False, index=h.index), why
```

**Result:** 40/41 tests pass. Failing: `test_commitment_rule_drops_only_unfunded_commitment_rows`.

```
AssertionError: [False, False, False, False]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 6. `rule_commitment_rows`, broken

**Break:** the no-cost/no-principal guard is removed, so a row carrying principal is dropped as a commitment.

```diff
- return t.str.contains(COMMITMENT_ROW, regex=True) & ~terms, why
+ return t.str.contains(COMMITMENT_ROW, regex=True), why
```

**Result:** 40/41 tests pass. Failing: `test_commitment_rule_drops_only_unfunded_commitment_rows`.

```
AssertionError: [True, False, True, False]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 7. `rule_jv_portfolio`, removed

**Break:** the rule drops nothing.

```diff
- return (h["subsidiary"].notna(),
+ return (pd.Series(False, index=h.index),
```

**Result:** 39/41 tests pass. Failing: `test_jv_portfolio_rule_drops_only_jv_rows`, `test_rollforward_rule_ignores_a_counterpart_already_dropped_as_jv`.

```
AssertionError: [False, False, False]
AssertionError: ['0']
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 8. `rule_jv_portfolio`, broken

**Break:** the rule tests the wrong column and drops every identified holding, not only rows on the Nonconsolidated Subsidiary Axis.

```diff
- return (h["subsidiary"].notna(),
+ return (h["identifier"].notna(),
```

**Result:** 35/41 tests pass. Failing: `test_checker_uses_release_and_row_together`, `test_combined_baseline_uses_one_copy_of_repeated_filings`, `test_jv_portfolio_rule_drops_only_jv_rows`, `test_reports_preserve_triage_and_flag_changed_totals`, `test_reports_reject_panel_mismatch_or_missing_provenance`, `test_rollforward_rule_ignores_a_counterpart_already_dropped_as_jv`.

```
AssertionError
AssertionError: DataFrame.iloc[:, 0] (column name="adsh") are different
AssertionError: [True, True, True]
IndexError: index 0 is out of bounds for axis 0 with size 0
AssertionError: []
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 9. `rule_issuer_subtotals`, removed

**Break:** the rule drops nothing.

```diff
- drop[idx[i]] = True
+ pass
```

**Result:** 40/41 tests pass. Failing: `test_issuer_subtotal_rule_drops_only_true_subtotals`.

```
AssertionError: [False, False, False, False, False, False, False, False, False, False, False]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 10. `rule_issuer_subtotals`, broken

**Break:** the sibling-tranche check is removed, so "Revolver One" / "Warrant 2" count as children of a parent line (the first-version bug).

```diff
- and not re.fullmatch(SIBLING_SUFFIX, rest, re.I)
+ 
```

**Result:** 40/41 tests pass. Failing: `test_issuer_subtotal_rule_drops_only_true_subtotals`.

```
AssertionError: [True, False, False, True, False, False, False, False, False, True, False]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 11. `rule_issuer_subtotals`, broken

**Break:** the sum tolerance is loosened from 0.2% to 5%, so a parent that only roughly equals its children is dropped.

```diff
- rel_tol: float = 0.002
+ rel_tol: float = 0.05
```

**Result:** 40/41 tests pass. Failing: `test_issuer_subtotal_rule_drops_only_true_subtotals`.

```
AssertionError: [True, False, False, False, False, False, False, True, False, True, False]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 12. `rule_issuer_subtotals`, broken

**Break:** the word-boundary check is removed, so "ABC" is treated as the parent of "ABCD LLC" (review finding P2).

```diff
- if (rest and not rest[0].isalnum()
+ if (rest
```

**Result:** 40/41 tests pass. Failing: `test_issuer_subtotal_rule_needs_a_real_name_boundary`.

```
AssertionError: [True, False, False, False]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 13. `rule_issuer_subtotals`, broken

**Break:** the company-suffix check is removed, so "XYZ" is treated as the parent of "XYZ, LLC" (review finding P2).

```diff
- and not re.fullmatch(COMPANY_SUFFIX, rest, re.I)):
+ ):
```

**Result:** 40/41 tests pass. Failing: `test_issuer_subtotal_rule_needs_a_real_name_boundary`.

```
AssertionError: [False, False, True, False]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 14. `rule_issuer_subtotals`, broken

**Break:** a parent that names an instrument may be dropped, so one loan is treated as the subtotal of another (review finding P2).

```diff
- if n_kids == 0 or instrument_kind(parent):
+ if n_kids == 0:
```

**Result:** 40/41 tests pass. Failing: `test_issuer_subtotal_rule_keeps_a_parent_that_names_an_instrument`.

```
AssertionError: [True, False]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 15. `rule_rollforward_copies`, removed

**Break:** the rule drops nothing.

```diff
- drop[ix] = True
+ pass
```

**Result:** 38/41 tests pass. Failing: `test_rollforward_copy_rule_drops_only_bare_twins`, `test_rollforward_evidence_is_an_opening_value_without_cost_or_principal`, `test_rollforward_rule_lets_one_holding_vouch_for_one_copy`.

```
AssertionError: [False, False, False, False, False]
AssertionError: [False, False]
AssertionError: [False, False, False]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 16. `rule_rollforward_copies`, broken

**Break:** the instrument check is removed, so preferred equity is dropped as a copy of a loan with the same value (review finding P1).

```diff
- if _compatible(kind[ix], k) and _compatible(form[ix], f):
+ if _compatible(form[ix], f):
```

**Result:** 40/41 tests pass. Failing: `test_rollforward_rule_keeps_a_distinct_instrument_with_the_same_value`.

```
AssertionError: [False, True]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 17. `rule_rollforward_copies`, broken

**Break:** the debt-form check is removed, so a revolver is dropped as a copy of a term loan with the same value (second review finding).

```diff
- if _compatible(kind[ix], k) and _compatible(form[ix], f):
+ if _compatible(kind[ix], k):
```

**Result:** 40/41 tests pass. Failing: `test_rollforward_rule_keeps_a_revolver_that_matches_a_term_loan_by_value`.

```
AssertionError: [False, True]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 18. `rule_rollforward_copies`, broken

**Break:** the roll-forward evidence requirement is removed, so any bare row is a candidate copy (second review finding).

```diff
- & h["rf_opening"].fillna(False).astype(bool))
+ )
```

**Result:** 40/41 tests pass. Failing: `test_rollforward_evidence_is_an_opening_value_without_cost_or_principal`.

```
AssertionError: [False, True]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 19. `rule_rollforward_copies`, broken

**Break:** a schedule holding may vouch for any number of copies, so two bare rows are dropped against one counterpart (review finding P1).

```diff
- del pool[n]          # one counterpart per copy
+ 
```

**Result:** 40/41 tests pass. Failing: `test_rollforward_rule_lets_one_holding_vouch_for_one_copy`.

```
AssertionError: [False, True, True]
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

### 20. `apply_rules`, broken

**Break:** every rule sees the original frame, so a JV loan already dropped still serves as the counterpart for a BDC holding (review finding P1).

```diff
- drop, why = rule(h[keep])
+ drop, why = rule(h)
```

**Result:** 40/41 tests pass. Failing: `test_rollforward_rule_ignores_a_counterpart_already_dropped_as_jv`.

```
AssertionError: []
```

**Restored:** `clean.py` written back; suite 41/41 tests pass.

## The same rules on the real quarter

The unit tests use small hand-made frames. `tools/rule_impact.py` shows each rule also matters on 2026q2: leaving it out changes which filings are admitted (`reports/rule_impact.csv`).

| Rule left out | Admitted filings (of 177) | Change |
|---|---:|---:|
| none (all rules) | 90 | |
| `rule_totals` | 89 | -1 |
| `rule_cash` | 89 | -1 |
| `rule_commitment_rows` | 90 | +0 |
| `rule_jv_portfolio` | 85 | -5 |
| `rule_issuer_subtotals` | 86 | -4 |
| `rule_rollforward_copies` | 85 | -5 |

## What this exercise found

The first run caught 10 of 11 breaks. Loosening `rule_issuer_subtotals`' tolerance from 0.2% to 5% left all 22 tests passing: the test's only "not a subtotal" case (Beta Corp, 70 vs 60) was 17% off, so any tolerance below 17% passed it. A loose tolerance was one of the two bugs in the rule's first version, so this mattered. `test_issuer_subtotal_rule_drops_only_true_subtotals` now pins the tolerance from both sides: Gamma Inc, 2% above its child, must be kept, and Delta LP, 0.1% above (a rounding difference), must be dropped. The rerun catches all 11 breaks.

Removing `rule_totals` or `rule_cash` also fails the starter kit's fixture tests (`test_baseline_reconciliation_counts_every_filing` and the two checker tests), because the fixture's expected admissions depend on those rules. The four new rules are caught by their own tests only: the fixture has no JV rows, issuer subtotals or roll-forward copies, so their evidence on real data is the table above.

Six of the breaks (marked *review finding*) reproduce the two problems Lokesh found reviewing PR #3: an unrestricted name prefix in `rule_issuer_subtotals` (P2), and in `rule_rollforward_copies` matching by issuer and value only, plus every rule seeing rows an earlier rule had dropped (P1). Each now has a regression test that fails on the pre-review code (23 of 28 pass there) and passes after the fix. Two more (marked *second review finding*) reproduce Lokesh's second review of 6fd1844: a revolver dropped as a copy of a same-value term loan, and bare rows treated as copies without roll-forward evidence.

## Known limitations no test covers

These are real cases where the rules do not give the right answer, recorded so nobody mistakes the passing suite for full correctness. Details are in `docs/cleaning_log.md`.

- **`rule_cash` matches the words "money market" anywhere** in an identifier, so a borrower with those words in its name would be dropped. None appears in 2026q2 (all matching lines were checked), but a later release could have one.
- **TriplePoint Private Venture Credit** (adsh 0001792509-26-000017) was admitted at +0.41% only because the starter `rule_totals` wrongly dropped a real $7.5M loan (Total Expert, Inc., SOI row 163022). With the fix it is +2.36% and not admitted: a separate ~$9.1M overcount remains, left for triage.
- **Lord Abbett Private Credit Fund S** (adsh 0000930413-26-001613, −5.66%) reports its joint-venture investment under the `Investments` tag (SOI row 17151, $21.608M, its exact shortfall). No rule recovers it: the same fallback also picks up a category subtotal and overshoots to +2.01%.
- **`rule_issuer_subtotals` and `rule_rollforward_copies` depend on identifier text.** A filer that names a parent line differently from its children, or restates a roll-forward value under a different issuer spelling, is not caught.
- **Custom-axis filings** (Partners Group, SuRo Capital) have no usable identifiers, so no rule applies to them; they are triaged.
