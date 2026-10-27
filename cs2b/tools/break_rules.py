"""Prove every cleaning-rule test can fail (Case Study 2B, Part 5).

For each rule: edit src/lookthrough/clean.py to remove or break the rule, run
`python tests/run_tests.py`, record which tests fail and why, restore the file
(checked byte-for-byte) and confirm the suite passes again. Writes
reports/tests_that_fail.md.

    python tools/break_rules.py
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "src" / "lookthrough" / "clean.py"
OUT = ROOT / "reports" / "tests_that_fail.md"

# (rule, kind, what the break does, exact text in clean.py, replacement)
BREAKS = [
    ("rule_totals", "removed", "the rule drops nothing",
     "return (_matches(h, TOTAL) & ~_matches(h, NOT_A_TOTAL),",
     "return (pd.Series(False, index=h.index),"),
    ("rule_totals", "broken", "the company-suffix / maturity-date guard is removed, "
     "so borrowers named \"Total ...\" are dropped again (the Total Expert bug)",
     "_matches(h, TOTAL) & ~_matches(h, NOT_A_TOTAL)",
     "_matches(h, TOTAL)"),
    ("rule_cash", "removed", "the rule drops nothing",
     "return (_matches(h, CASH) & ~_matches(h, SHORT_TERM_INV),",
     "return (pd.Series(False, index=h.index),"),
    ("rule_cash", "broken", "the short-term-investment exception is removed, so the "
     "filer-aware rule falls back to the starter behaviour (Palmer Square, Great Elm fail again)",
     "_matches(h, CASH) & ~_matches(h, SHORT_TERM_INV)",
     "_matches(h, CASH)"),
    ("rule_jv_portfolio", "removed", "the rule drops nothing",
     "return (h[\"subsidiary\"].notna(),",
     "return (pd.Series(False, index=h.index),"),
    ("rule_jv_portfolio", "broken", "the rule tests the wrong column and drops every "
     "identified holding, not only rows on the Nonconsolidated Subsidiary Axis",
     "return (h[\"subsidiary\"].notna(),",
     "return (h[\"identifier\"].notna(),"),
    ("rule_issuer_subtotals", "removed", "the rule drops nothing",
     "drop[idx[i]] = True",
     "pass"),
    ("rule_issuer_subtotals", "broken", "the sibling-tranche check is removed, so "
     "\"Revolver One\" / \"Warrant 2\" count as children of a parent line (the first-version bug)",
     "and not re.fullmatch(SIBLING_SUFFIX, rest, re.I)",
     ""),
    ("rule_issuer_subtotals", "broken", "the sum tolerance is loosened from 0.2% to 5%, "
     "so a parent that only roughly equals its children is dropped",
     "rel_tol: float = 0.002",
     "rel_tol: float = 0.05"),
    ("rule_issuer_subtotals", "broken", "the word-boundary check is removed, so \"ABC\" "
     "is treated as the parent of \"ABCD LLC\" (review finding P2)",
     "if (rest and not rest[0].isalnum()",
     "if (rest"),
    ("rule_issuer_subtotals", "broken", "the company-suffix check is removed, so \"XYZ\" "
     "is treated as the parent of \"XYZ, LLC\" (review finding P2)",
     "and not re.fullmatch(COMPANY_SUFFIX, rest, re.I)):",
     "):"),
    ("rule_issuer_subtotals", "broken", "a parent that names an instrument may be dropped, "
     "so one loan is treated as the subtotal of another (review finding P2)",
     "if n_kids == 0 or instrument_kind(parent):",
     "if n_kids == 0:"),
    ("rule_rollforward_copies", "removed", "the rule drops nothing",
     "                drop[ix] = True\n",
     "                pass\n"),
    ("rule_rollforward_copies", "broken", "the instrument check is removed, so preferred "
     "equity is dropped as a copy of a loan with the same value (review finding P1)",
     "if _compatible(kind[ix], k) and _compatible(form[ix], f):",
     "if _compatible(form[ix], f):"),
    ("rule_rollforward_copies", "broken", "the debt-form check is removed, so a revolver "
     "is dropped as a copy of a term loan with the same value (second review finding)",
     "if _compatible(kind[ix], k) and _compatible(form[ix], f):",
     "if _compatible(kind[ix], k):"),
    ("rule_rollforward_copies", "broken", "the roll-forward evidence requirement is removed, "
     "so any bare row is a candidate copy (second review finding)",
     "            & h[\"rf_opening\"].fillna(False).astype(bool))",
     ")"),
    ("rule_rollforward_copies", "broken", "a schedule holding may vouch for any number of "
     "copies, so two bare rows are dropped against one counterpart (review finding P1)",
     "                del pool[n]          # one counterpart per copy\n",
     ""),
    ("apply_rules", "broken", "every rule sees the original frame, so a JV loan already "
     "dropped still serves as the counterpart for a BDC holding (review finding P1)",
     "drop, why = rule(h[keep])",
     "drop, why = rule(h)"),
]

# rule_impact.csv evidence: admitted filings on the real quarter with all rules
# and with each rule left out (written by tools/rule_impact.py).
IMPACT = ROOT / "reports" / "rule_impact.csv"


def run_tests():
    p = subprocess.run([sys.executable, "tests/run_tests.py"], cwd=ROOT,
                       capture_output=True, text=True)
    out = p.stdout + p.stderr
    fails = re.findall(r"^\s*FAIL\s+(\S+)", out, re.M)
    summary = re.findall(r"^(\d+/\d+ tests pass)", out, re.M)
    # the last line of each traceback: the assertion that tripped
    reasons = re.findall(r"^(AssertionError.*|\w+Error: .*)$", out, re.M)
    return p.returncode, fails, summary[-1] if summary else "?", reasons, out


def sha(b):
    return hashlib.sha256(b).hexdigest()


def coverage_lines():
    if not IMPACT.exists():
        return []
    import pandas as pd
    t = pd.read_csv(IMPACT, dtype={"adsh": str})
    adm = [c for c in t.columns if c.startswith("admitted")]
    if "admitted" not in t:
        return []
    lines = ["| Rule left out | Admitted filings (of %d) | Change |" % len(t),
             "|---|---:|---:|",
             "| none (all rules) | %d | |" % int(t["admitted"].sum())]
    for c in adm:
        if c == "admitted":
            continue
        rule = c.replace("admitted_without_", "")
        n = int(t[c].sum())
        lines.append(f"| `{rule}` | {n} | {n - int(t['admitted'].sum()):+d} |")
    return lines


def main():
    original = CLEAN.read_bytes()
    code, fails, summary, _, _ = run_tests()
    if code != 0:
        sys.exit(f"suite must pass before breaking rules: {summary}, failing {fails}")
    base_summary = summary
    results = []
    try:
        for rule, kind, what, old, new in BREAKS:
            src = original.decode()
            if src.count(old) != 1:
                sys.exit(f"{rule}/{kind}: target text found {src.count(old)} times")
            CLEAN.write_text(src.replace(old, new))
            code, fails, summary, reasons, _ = run_tests()
            CLEAN.write_bytes(original)
            results.append(dict(rule=rule, kind=kind, what=what, old=old, new=new,
                                code=code, fails=fails, summary=summary,
                                reasons=reasons))
            print(f"{rule:24s} {kind:8s} -> {summary}; failing: {', '.join(fails) or 'NONE'}")
    finally:
        CLEAN.write_bytes(original)
    restored = sha(CLEAN.read_bytes()) == sha(original)
    code, fails, after, _, _ = run_tests()
    caught = all(r["code"] != 0 for r in results)
    print(f"restored byte-identical: {restored}; after restore: {after}; every break caught: {caught}")

    L = ["# Tests that fail", "",
         "A test is evidence only if it can fail. For every cleaning rule we broke the rule "
         "in `src/lookthrough/clean.py`, ran `python tests/run_tests.py`, recorded the "
         "failures, restored the file and re-ran the suite.",
         "",
         "Each rule is broken two ways: **removed** (the rule drops nothing) and **broken** "
         "(one realistic bug, usually a mistake we made and fixed while writing the rule). "
         "The run is automated and repeatable:", "",
         "```", "python tools/break_rules.py", "```", "",
         f"- Suite before breaking: **{base_summary}**",
         f"- Breaks applied: **{len(results)}**; caught by at least one failing test: "
         f"**{sum(r['code'] != 0 for r in results)} of {len(results)}**",
         f"- `clean.py` restored byte-identical after the run: **{restored}**",
         f"- Suite after restoring: **{after}**", "",
         "## Summary", "",
         "| Rule | Break | Result | Failing test(s) |", "|---|---|---|---|"]
    for r in results:
        L.append(f"| `{r['rule']}` | {r['kind']}: {r['what']} | {r['summary']} | "
                 + (", ".join(f"`{f}`" for f in r["fails"]) or "**none: not caught**") + " |")
    L += ["", "## Each break", ""]
    for i, r in enumerate(results, 1):
        L += [f"### {i}. `{r['rule']}`, {r['kind']}", "",
              f"**Break:** {r['what']}.", "",
              "```diff", f"- {r['old'].strip()}", f"+ {r['new'].strip()}", "```", "",
              f"**Result:** {r['summary']}. Failing: "
              + (", ".join(f"`{f}`" for f in r["fails"]) or "none") + ".", ""]
        if r["reasons"]:
            L += ["```"] + [x[:300] for x in dict.fromkeys(r["reasons"])] + ["```", ""]
        L += [f"**Restored:** `clean.py` written back; suite {after}.", ""]
    cov = coverage_lines()
    if cov:
        L += ["## The same rules on the real quarter", "",
              "The unit tests use small hand-made frames. `tools/rule_impact.py` shows each "
              "rule also matters on 2026q2: leaving it out changes which filings are admitted "
              "(`reports/rule_impact.csv`).", ""] + cov + [""]
    L += ["## What this exercise found", "",
          "The first run caught 10 of 11 breaks. Loosening `rule_issuer_subtotals`' tolerance "
          "from 0.2% to 5% left all 22 tests passing: the test's only \"not a subtotal\" case "
          "(Beta Corp, 70 vs 60) was 17% off, so any tolerance below 17% passed it. A loose "
          "tolerance was one of the two bugs in the rule's first version, so this mattered. "
          "`test_issuer_subtotal_rule_drops_only_true_subtotals` now pins the tolerance from "
          "both sides: Gamma Inc, 2% above its child, must be kept, and Delta LP, 0.1% above "
          "(a rounding difference), must be dropped. The rerun catches all 11 breaks.", "",
          "Removing `rule_totals` or `rule_cash` also fails the starter kit's fixture tests "
          "(`test_baseline_reconciliation_counts_every_filing` and the two checker tests), "
          "because the fixture's expected admissions depend on those rules. The four new "
          "rules are caught by their own tests only: the fixture has no JV rows, issuer "
          "subtotals or roll-forward copies, so their evidence on real data is the table above.", "",
          "Six of the breaks (marked *review finding*) reproduce the two problems Lokesh found "
          "reviewing PR #3: an unrestricted name prefix in `rule_issuer_subtotals` (P2), and in "
          "`rule_rollforward_copies` matching by issuer and value only, plus every rule seeing "
          "rows an earlier rule had dropped (P1). Each now has a regression test that fails on "
          "the pre-review code (23 of 28 pass there) and passes after the fix. Two more "
          "(marked *second review finding*) reproduce Lokesh's second review of 6fd1844: a "
          "revolver dropped as a copy of a same-value term loan, and bare rows treated as "
          "copies without roll-forward evidence.", ""]
    L += ["## Known limitations no test covers", "",
          "These are real cases where the rules do not give the right answer, recorded so "
          "nobody mistakes the passing suite for full correctness. Details are in "
          "`docs/cleaning_log.md`.", "",
          "- **`rule_cash` matches the words \"money market\" anywhere** in an identifier, so "
          "a borrower with those words in its name would be dropped. None appears in 2026q2 "
          "(all matching lines were checked), but a later release could have one.",
          "- **TriplePoint Private Venture Credit** (adsh 0001792509-26-000017) was admitted "
          "at +0.41% only because the starter `rule_totals` wrongly dropped a real $7.5M "
          "loan (Total Expert, Inc., SOI row 163022). With the fix it is +2.36% and not "
          "admitted: a separate ~$9.1M overcount remains, left for triage.",
          "- **Lord Abbett Private Credit Fund S** (adsh 0000930413-26-001613, −5.66%) reports "
          "its joint-venture investment under the `Investments` tag (SOI row 17151, $21.608M, "
          "its exact shortfall). No rule recovers it: the same fallback also picks up a "
          "category subtotal and overshoots to +2.01%.",
          "- **`rule_issuer_subtotals` and `rule_rollforward_copies` depend on identifier "
          "text.** A filer that names a parent line differently from its children, or "
          "restates a roll-forward value under a different issuer spelling, is not caught.",
          "- **Custom-axis filings** (Partners Group, SuRo Capital) have no usable "
          "identifiers, so no rule applies to them; they are triaged.", ""]
    OUT.write_text("\n".join(L))
    print(f"wrote {OUT.relative_to(ROOT)}")
    sys.exit(0 if (restored and code == 0 and caught) else 1)


if __name__ == "__main__":
    main()
