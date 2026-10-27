# Tests that fail

A test is evidence only if it can fail. For every cleaning rule we broke the rule in `src/lookthrough/clean.py`, ran `python tests/run_tests.py`, recorded the failures, restored the file and re-ran the suite.

Each rule is broken two ways: **removed** (the rule drops nothing) and **broken** (one realistic bug, usually a mistake we made and fixed while writing the rule). The run is automated and repeatable:

```
python tools/break_rules.py
```

- Suite before breaking: **30/30 tests pass**
- Breaks applied: **18**; caught by at least one failing test: **18 of 18**
- `clean.py` restored byte-identical after the run: **True**
- Suite after restoring: **30/30 tests pass**

## Summary

| Rule | Break | Result | Failing test(s) |
|---|---|---|---|
| `rule_totals` | removed: the rule drops nothing | 25/30 tests pass | `test_baseline_reconciliation_counts_every_filing`, `test_checker_catches_a_silently_dropped_filing`, `test_checker_passes_baseline_and_catches_tampering`, `test_total_rule_spares_companies_named_total`, `test_total_rule_spares_ordinary_names` |
| `rule_totals` | broken: the company-suffix / maturity-date guard is removed, so borrowers named "Total ..." are dropped again (the Total Expert bug) | 29/30 tests pass | `test_total_rule_spares_companies_named_total` |
| `rule_cash` | removed: the rule drops nothing | 26/30 tests pass | `test_baseline_reconciliation_counts_every_filing`, `test_cash_rule_keeps_money_market_labelled_short_term_investment`, `test_checker_catches_a_silently_dropped_filing`, `test_checker_passes_baseline_and_catches_tampering` |
| `rule_cash` | broken: the short-term-investment exception is removed, so the filer-aware rule falls back to the starter behaviour (Palmer Square, Great Elm fail again) | 29/30 tests pass | `test_cash_rule_keeps_money_market_labelled_short_term_investment` |
| `rule_jv_portfolio` | removed: the rule drops nothing | 28/30 tests pass | `test_jv_portfolio_rule_drops_only_jv_rows`, `test_rollforward_rule_ignores_a_counterpart_already_dropped_as_jv` |
| `rule_jv_portfolio` | broken: the rule tests the wrong column and drops every identified holding, not only rows on the Nonconsolidated Subsidiary Axis | 28/30 tests pass | `test_jv_portfolio_rule_drops_only_jv_rows`, `test_rollforward_rule_ignores_a_counterpart_already_dropped_as_jv` |
| `rule_issuer_subtotals` | removed: the rule drops nothing | 29/30 tests pass | `test_issuer_subtotal_rule_drops_only_true_subtotals` |
| `rule_issuer_subtotals` | broken: the sibling-tranche check is removed, so "Revolver One" / "Warrant 2" count as children of a parent line (the first-version bug) | 29/30 tests pass | `test_issuer_subtotal_rule_drops_only_true_subtotals` |
| `rule_issuer_subtotals` | broken: the sum tolerance is loosened from 0.2% to 5%, so a parent that only roughly equals its children is dropped | 29/30 tests pass | `test_issuer_subtotal_rule_drops_only_true_subtotals` |
| `rule_issuer_subtotals` | broken: the word-boundary check is removed, so "ABC" is treated as the parent of "ABCD LLC" (review finding P2) | 29/30 tests pass | `test_issuer_subtotal_rule_needs_a_real_name_boundary` |
| `rule_issuer_subtotals` | broken: the company-suffix check is removed, so "XYZ" is treated as the parent of "XYZ, LLC" (review finding P2) | 29/30 tests pass | `test_issuer_subtotal_rule_needs_a_real_name_boundary` |
| `rule_issuer_subtotals` | broken: a parent that names an instrument may be dropped, so one loan is treated as the subtotal of another (review finding P2) | 29/30 tests pass | `test_issuer_subtotal_rule_keeps_a_parent_that_names_an_instrument` |
| `rule_rollforward_copies` | removed: the rule drops nothing | 27/30 tests pass | `test_rollforward_copy_rule_drops_only_bare_twins`, `test_rollforward_evidence_is_an_opening_value_without_cost_or_principal`, `test_rollforward_rule_lets_one_holding_vouch_for_one_copy` |
| `rule_rollforward_copies` | broken: the instrument check is removed, so preferred equity is dropped as a copy of a loan with the same value (review finding P1) | 29/30 tests pass | `test_rollforward_rule_keeps_a_distinct_instrument_with_the_same_value` |
| `rule_rollforward_copies` | broken: the debt-form check is removed, so a revolver is dropped as a copy of a term loan with the same value (second review finding) | 29/30 tests pass | `test_rollforward_rule_keeps_a_revolver_that_matches_a_term_loan_by_value` |
| `rule_rollforward_copies` | broken: the roll-forward evidence requirement is removed, so any bare row is a candidate copy (second review finding) | 29/30 tests pass | `test_rollforward_evidence_is_an_opening_value_without_cost_or_principal` |
| `rule_rollforward_copies` | broken: a schedule holding may vouch for any number of copies, so two bare rows are dropped against one counterpart (review finding P1) | 29/30 tests pass | `test_rollforward_rule_lets_one_holding_vouch_for_one_copy` |
| `apply_rules` | broken: every rule sees the original frame, so a JV loan already dropped still serves as the counterpart for a BDC holding (review finding P1) | 29/30 tests pass | `test_rollforward_rule_ignores_a_counterpart_already_dropped_as_jv` |

## Each break

### 1. `rule_totals`, removed

**Break:** the rule drops nothing.

```diff
- return (_matches(h, TOTAL) & ~_matches(h, NOT_A_TOTAL),
+ return (pd.Series(False, index=h.index),
```

**Result:** 25/30 tests pass. Failing: `test_baseline_reconciliation_counts_every_filing`, `test_checker_catches_a_silently_dropped_filing`, `test_checker_passes_baseline_and_catches_tampering`, `test_total_rule_spares_companies_named_total`, `test_total_rule_spares_ordinary_names`.

```
AssertionError
AssertionError: ['every filing with SOI rows is in coverage.csv (none dropped)', 'every excluded filing has a valid triage_category']
AssertionError: [('every excluded filing has a valid triage_category', False, "found ['to_triage']; allowed: comparative_leakage, totals_counted, cash_lines, restated_copies, unfunded_commitments, custom_tags, no_identified_holdings, affiliate_split, no_filed_total, other")]
AssertionError: [False, False, False, False, False]
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 2. `rule_totals`, broken

**Break:** the company-suffix / maturity-date guard is removed, so borrowers named "Total ..." are dropped again (the Total Expert bug).

```diff
- _matches(h, TOTAL) & ~_matches(h, NOT_A_TOTAL)
+ _matches(h, TOTAL)
```

**Result:** 29/30 tests pass. Failing: `test_total_rule_spares_companies_named_total`.

```
AssertionError: [True, True, True, True, True]
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 3. `rule_cash`, removed

**Break:** the rule drops nothing.

```diff
- return (_matches(h, CASH) & ~_matches(h, SHORT_TERM_INV),
+ return (pd.Series(False, index=h.index),
```

**Result:** 26/30 tests pass. Failing: `test_baseline_reconciliation_counts_every_filing`, `test_cash_rule_keeps_money_market_labelled_short_term_investment`, `test_checker_catches_a_silently_dropped_filing`, `test_checker_passes_baseline_and_catches_tampering`.

```
AssertionError
AssertionError: [False, False]
AssertionError: ['every filing with SOI rows is in coverage.csv (none dropped)', 'every excluded filing has a valid triage_category']
AssertionError: [('every excluded filing has a valid triage_category', False, "found ['to_triage']; allowed: comparative_leakage, totals_counted, cash_lines, restated_copies, unfunded_commitments, custom_tags, no_identified_holdings, affiliate_split, no_filed_total, other")]
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 4. `rule_cash`, broken

**Break:** the short-term-investment exception is removed, so the filer-aware rule falls back to the starter behaviour (Palmer Square, Great Elm fail again).

```diff
- _matches(h, CASH) & ~_matches(h, SHORT_TERM_INV)
+ _matches(h, CASH)
```

**Result:** 29/30 tests pass. Failing: `test_cash_rule_keeps_money_market_labelled_short_term_investment`.

```
AssertionError: [True, True]
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 5. `rule_jv_portfolio`, removed

**Break:** the rule drops nothing.

```diff
- return (h["subsidiary"].notna(),
+ return (pd.Series(False, index=h.index),
```

**Result:** 28/30 tests pass. Failing: `test_jv_portfolio_rule_drops_only_jv_rows`, `test_rollforward_rule_ignores_a_counterpart_already_dropped_as_jv`.

```
AssertionError: [False, False, False]
AssertionError: ['0']
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 6. `rule_jv_portfolio`, broken

**Break:** the rule tests the wrong column and drops every identified holding, not only rows on the Nonconsolidated Subsidiary Axis.

```diff
- return (h["subsidiary"].notna(),
+ return (h["identifier"].notna(),
```

**Result:** 28/30 tests pass. Failing: `test_jv_portfolio_rule_drops_only_jv_rows`, `test_rollforward_rule_ignores_a_counterpart_already_dropped_as_jv`.

```
AssertionError: [True, True, True]
AssertionError: []
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 7. `rule_issuer_subtotals`, removed

**Break:** the rule drops nothing.

```diff
- drop[idx[i]] = True
+ pass
```

**Result:** 29/30 tests pass. Failing: `test_issuer_subtotal_rule_drops_only_true_subtotals`.

```
AssertionError: [False, False, False, False, False, False, False, False, False, False, False]
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 8. `rule_issuer_subtotals`, broken

**Break:** the sibling-tranche check is removed, so "Revolver One" / "Warrant 2" count as children of a parent line (the first-version bug).

```diff
- and not re.fullmatch(SIBLING_SUFFIX, rest, re.I)
+ 
```

**Result:** 29/30 tests pass. Failing: `test_issuer_subtotal_rule_drops_only_true_subtotals`.

```
AssertionError: [True, False, False, True, False, False, False, False, False, True, False]
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 9. `rule_issuer_subtotals`, broken

**Break:** the sum tolerance is loosened from 0.2% to 5%, so a parent that only roughly equals its children is dropped.

```diff
- rel_tol: float = 0.002
+ rel_tol: float = 0.05
```

**Result:** 29/30 tests pass. Failing: `test_issuer_subtotal_rule_drops_only_true_subtotals`.

```
AssertionError: [True, False, False, False, False, False, False, True, False, True, False]
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 10. `rule_issuer_subtotals`, broken

**Break:** the word-boundary check is removed, so "ABC" is treated as the parent of "ABCD LLC" (review finding P2).

```diff
- if (rest and not rest[0].isalnum()
+ if (rest
```

**Result:** 29/30 tests pass. Failing: `test_issuer_subtotal_rule_needs_a_real_name_boundary`.

```
AssertionError: [True, False, False, False]
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 11. `rule_issuer_subtotals`, broken

**Break:** the company-suffix check is removed, so "XYZ" is treated as the parent of "XYZ, LLC" (review finding P2).

```diff
- and not re.fullmatch(COMPANY_SUFFIX, rest, re.I)):
+ ):
```

**Result:** 29/30 tests pass. Failing: `test_issuer_subtotal_rule_needs_a_real_name_boundary`.

```
AssertionError: [False, False, True, False]
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 12. `rule_issuer_subtotals`, broken

**Break:** a parent that names an instrument may be dropped, so one loan is treated as the subtotal of another (review finding P2).

```diff
- if n_kids == 0 or instrument_kind(parent):
+ if n_kids == 0:
```

**Result:** 29/30 tests pass. Failing: `test_issuer_subtotal_rule_keeps_a_parent_that_names_an_instrument`.

```
AssertionError: [True, False]
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 13. `rule_rollforward_copies`, removed

**Break:** the rule drops nothing.

```diff
- drop[ix] = True
+ pass
```

**Result:** 27/30 tests pass. Failing: `test_rollforward_copy_rule_drops_only_bare_twins`, `test_rollforward_evidence_is_an_opening_value_without_cost_or_principal`, `test_rollforward_rule_lets_one_holding_vouch_for_one_copy`.

```
AssertionError: [False, False, False, False, False]
AssertionError: [False, False]
AssertionError: [False, False, False]
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 14. `rule_rollforward_copies`, broken

**Break:** the instrument check is removed, so preferred equity is dropped as a copy of a loan with the same value (review finding P1).

```diff
- if _compatible(kind[ix], k) and _compatible(form[ix], f):
+ if _compatible(form[ix], f):
```

**Result:** 29/30 tests pass. Failing: `test_rollforward_rule_keeps_a_distinct_instrument_with_the_same_value`.

```
AssertionError: [False, True]
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 15. `rule_rollforward_copies`, broken

**Break:** the debt-form check is removed, so a revolver is dropped as a copy of a term loan with the same value (second review finding).

```diff
- if _compatible(kind[ix], k) and _compatible(form[ix], f):
+ if _compatible(kind[ix], k):
```

**Result:** 29/30 tests pass. Failing: `test_rollforward_rule_keeps_a_revolver_that_matches_a_term_loan_by_value`.

```
AssertionError: [False, True]
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 16. `rule_rollforward_copies`, broken

**Break:** the roll-forward evidence requirement is removed, so any bare row is a candidate copy (second review finding).

```diff
- & h["rf_opening"].fillna(False).astype(bool))
+ )
```

**Result:** 29/30 tests pass. Failing: `test_rollforward_evidence_is_an_opening_value_without_cost_or_principal`.

```
AssertionError: [False, True]
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 17. `rule_rollforward_copies`, broken

**Break:** a schedule holding may vouch for any number of copies, so two bare rows are dropped against one counterpart (review finding P1).

```diff
- del pool[n]          # one counterpart per copy
+ 
```

**Result:** 29/30 tests pass. Failing: `test_rollforward_rule_lets_one_holding_vouch_for_one_copy`.

```
AssertionError: [False, True, True]
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

### 18. `apply_rules`, broken

**Break:** every rule sees the original frame, so a JV loan already dropped still serves as the counterpart for a BDC holding (review finding P1).

```diff
- drop, why = rule(h[keep])
+ drop, why = rule(h)
```

**Result:** 29/30 tests pass. Failing: `test_rollforward_rule_ignores_a_counterpart_already_dropped_as_jv`.

```
AssertionError: []
```

**Restored:** `clean.py` written back; suite 30/30 tests pass.

## The same rules on the real quarter

The unit tests use small hand-made frames. `tools/rule_impact.py` shows each rule also matters on 2026q2: leaving it out changes which filings are admitted (`reports/rule_impact.csv`).

| Rule left out | Admitted filings (of 177) | Change |
|---|---:|---:|
| none (all rules) | 90 | |
| `rule_totals` | 89 | -1 |
| `rule_cash` | 89 | -1 |
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
