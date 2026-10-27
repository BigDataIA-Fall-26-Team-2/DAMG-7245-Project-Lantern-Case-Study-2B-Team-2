"""Tests for the lookthrough helpers, on the synthetic fixture. Run: pytest -q  (or python tests/run_tests.py)"""
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import acquire, check, clean, holdings, load, mapping, paths, pipeline, reconcile, report  # noqa: E402

P = paths.load_params(ROOT)
RDIR = ROOT / "data" / "fixture" / f"{paths.FIXTURE_RELEASE}_bdc"
NAMES = ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT"]


def by_name(df):
    return {n: df[df["name"].str.contains(n)].iloc[0] for n in NAMES if df["name"].str.contains(n).any()}


def test_norm_date_handles_three_formats():
    s = load.norm_date(pd.Series(["20260630", "06/30/2026", "2026-06-30", "6/3/2026", "bad", None]))
    assert list(s[:4]) == ["2026-06-30", "2026-06-30", "2026-06-30", "2026-06-03"]
    assert s[4:].isna().all()


def test_parse_segments_readme_examples():
    seg = ("InvestmentIssuerAffiliationAxis(us-gaap/2025)=InvestmentUnaffiliatedIssuerMember(us-gaap/2025);"
           "InvestmentIdentifierAxis(us-gaap/2025)=Senior Secured Loan | XYZ Corp (dba Foo)()")
    assert mapping.parse_segments(seg) == {"InvestmentIssuerAffiliationAxis": "InvestmentUnaffiliatedIssuerMember",
                                           "InvestmentIdentifierAxis": "Senior Secured Loan | XYZ Corp (dba Foo)"}
    assert mapping.parse_segments("") == {} and mapping.parse_segments(None) == {}


def test_release_url_patterns():
    assert acquire.release_url("2026_08").endswith("/business-development-company-bdc-data-sets/2026_08_bdc.zip")
    assert acquire.release_url("2025q4").endswith("/2025q4_bdc.zip")


def test_placeholder_user_agent_is_refused():
    for ua in ("no email here", "Your Name your.email@northeastern.edu"):
        try:
            acquire.download_release("2026_08", tempfile.gettempdir(), ua)
            assert False, "should have raised"
        except ValueError:
            pass


def test_columns_map_by_tag_and_usecols_cover_them():
    header, tag = load.soi_header(RDIR), load.load_tag(RDIR)
    cm = mapping.map_soi_columns(header, tag)
    assert set(cm) == set(mapping.CANONICAL)
    cols = mapping.soi_usecols(header, cm)
    assert all(c in cols for v in cm.values() for c in v) and "adsh" in cols


def test_soi_rows_keep_their_numbers_when_columns_are_limited():
    full, few = load.load_soi(RDIR), load.load_soi(RDIR, usecols=["adsh", "Investment Owned, Fair Value"])
    assert list(full["soi_row"]) == list(few["soi_row"]) and list(few.columns) == ["soi_row", "adsh", "Investment Owned, Fair Value"]


def test_superseded_filing_is_dropped():
    assert "0009000002-26-000201" not in set(load.load_sub(RDIR)["adsh"])


def test_current_period_comes_from_sub_when_soi_period_is_empty():
    sub = load.load_sub(RDIR)
    df = pd.DataFrame({"adsh": [sub["adsh"].iloc[0]] * 2, "ddate": ["2026-06-30", "2025-12-31"], "period": [pd.NA, pd.NA]})
    out = holdings.split_periods(df, sub)
    assert list(out["is_current"]) == [True, False]


def test_lean_num_keeps_custom_fair_value_facts():
    num = load.load_num(RDIR, tags=[reconcile.FV_TAG], custom_fv=True)
    assert set(num["tag"]) == {reconcile.FV_TAG, "InvestmentFairValueCustom"}


def test_split_rows_coalesce_to_one_row_per_holding():
    kept = pipeline.run_baseline(RDIR, 0.01)["kept"]
    alpha = kept[kept["name"].str.contains("ALPHA")]
    assert len(alpha) == 8 and (alpha["n_rows"] == 3).all() and alpha["fair_value"].notna().all()


def test_total_rule_spares_ordinary_names():
    h = pd.DataFrame({"identifier": ["Total Investments", "Subtotal First Lien", "First Lien | Totalcare Health LLC"],
                      "adsh": ["x"] * 3, "source_rows": ["1", "2", "3"]})
    drop, _ = clean.rule_totals(h)
    assert list(drop) == [True, True, False]


def test_baseline_reconciliation_counts_every_filing():
    B = pipeline.run_baseline(RDIR, 0.01)
    rec = by_name(B["rec"])
    assert [bool(rec[n]["admitted"]) for n in NAMES] == [True, True, True, False, False, False]
    assert abs(rec["DELTA"]["gap_pct"] - 0.020479) < 1e-5
    assert rec["FOXTROT"]["n_holdings"] == 0                       # counted, not silently dropped
    cov = reconcile.coverage(B["rec"], B["sub"])
    assert (cov["filings_attempted"], cov["filings_admitted"], cov["share_of_dollars"]) == (6, 3, 0.618)
    d = by_name(B["diag"])
    assert d["DELTA"]["negative_type_level_fv"] == -3_000_000
    assert d["ECHO"]["custom_fv_facts_in_num"] == 3 and d["ECHO"]["missing_fv_rows"] == 3
    assert d["FOXTROT"]["rows_without_identifier"] == 3
    # The pipeline runs clean.RULES; the three Part 2 rules find nothing in
    # the fixture (no JV rows, issuer subtotals or roll-forward copies).
    assert list(B["log"]["rule"]) == [r.__name__ for r in clean.RULES]
    assert list(B["log"]["rows_affected"]) == [1, 1, 0, 0, 0]


def test_manifest_is_portable_and_detects_changes():
    with tempfile.TemporaryDirectory() as t:
        root = Path(t) / "a"; (root / "data").mkdir(parents=True)
        f = root / "data" / "x.tsv"; f.write_text("a\tb\n1\t2\n")
        rows = acquire.write_manifest([f], root / "data" / "m.json", root=root)
        assert rows[0]["path"] == "data/x.tsv"
        moved = Path(t) / "b"; shutil.copytree(root, moved)          # a grader's clone, elsewhere
        assert acquire.verify_manifest(moved / "data" / "m.json", root=moved) == []
        (moved / "data" / "x.tsv").write_text("a\tb\n1\t3\n")
        assert acquire.verify_manifest(moved / "data" / "m.json", root=moved) == ["data/x.tsv"]


def test_unzip_handles_macos_entries_and_nesting():
    with tempfile.TemporaryDirectory() as t:
        z = Path(t) / "r.zip"
        with zipfile.ZipFile(z, "w") as zz:
            zz.writestr("odd_name/soi.tsv", "adsh\n"); zz.writestr("odd_name/datasets/sub.tsv", "adsh\n")
            zz.writestr("__MACOSX/odd_name/._soi.tsv", "junk"); zz.writestr("__MACOSX/odd_name/soi.tsv", "junk")
        out = acquire.unzip_release(z, Path(t) / "raw", "2026_08")
        assert out.name == "2026_08_bdc" and (out / "soi.tsv").exists() and (out / "datasets" / "sub.tsv").exists()


TRIAGED = {"DELTA": "unfunded_commitments", "ECHO": "custom_tags", "FOXTROT": "no_identified_holdings"}


def _outputs_in_temp_repo(t, triage=True):
    root = Path(t)
    import yaml
    p = dict(P); p["data"] = {**P["data"], "use_fixture": True}
    (root / "params.yaml").write_text(yaml.safe_dump(p))
    shutil.copytree(ROOT / "data" / "fixture", root / "data" / "fixture")
    B = pipeline.run_baseline(root / "data" / "fixture" / f"{paths.FIXTURE_RELEASE}_bdc", 0.01)
    report.write_outputs(B["kept"], B["rec"], B["diag"], B["log"], root, P)
    if triage:                                     # what a team does after investigating each exclusion
        cov = pd.read_csv(root / "reports" / "coverage.csv", dtype={"adsh": str})
        for k, v in TRIAGED.items():
            cov.loc[cov["name"].str.contains(k), "triage_category"] = v
        cov.to_csv(root / "reports" / "coverage.csv", index=False)
    return root


def test_checker_requires_triage_categories():
    with tempfile.TemporaryDirectory() as t:
        root = _outputs_in_temp_repo(t, triage=False)
        failed = [n for n, ok, _ in check.run_checks(root) if not ok]
        assert failed == ["every excluded filing has a valid triage_category"], failed


def test_checker_passes_baseline_and_catches_tampering():
    with tempfile.TemporaryDirectory() as t:
        root = _outputs_in_temp_repo(t)
        res = check.run_checks(root)
        assert all(ok for _, ok, _ in res), [r for r in res if not r[1]]
        assert (root / "reports" / "coverage.json").exists()
        cov = pd.read_csv(root / "reports" / "coverage.csv", dtype={"adsh": str})
        cov.loc[0, "holdings_fv"] += 5_000_000          # tamper: claim more than the panel holds
        cov.to_csv(root / "reports" / "coverage.csv", index=False)
        assert not all(ok for _, ok, _ in check.run_checks(root))


def test_checker_catches_a_silently_dropped_filing():
    with tempfile.TemporaryDirectory() as t:
        root = _outputs_in_temp_repo(t)
        cov = pd.read_csv(root / "reports" / "coverage.csv", dtype={"adsh": str})
        cov[~cov["name"].str.contains("FOXTROT")].to_csv(root / "reports" / "coverage.csv", index=False)
        failed = [n for n, ok, _ in check.run_checks(root) if not ok]
        assert failed == ["every filing with SOI rows is in coverage.csv (none dropped)"], failed


def test_jv_portfolio_rule_drops_only_jv_rows():
    # Same loan held by the BDC and listed again inside a JV's portfolio:
    # only the JV copy is dropped.
    h = pd.DataFrame({
        "adsh": ["A", "A", "A"],
        "identifier": ["First Lien Loan | Acme Corp",
                       "First Lien Loan | Acme Corp",
                       "Equity | Senior Loan Fund JV LLC"],
        "subsidiary": [pd.NA, "Senior Loan Fund JV LLC", pd.NA],
        "source_rows": ["1", "2", "3"]})
    drop, why = clean.rule_jv_portfolio(h)
    assert drop.tolist() == [False, True, False], drop.tolist()
    assert "JV" in why
    # Without a subsidiary column (e.g. the starter key) nothing is dropped.
    drop2, _ = clean.rule_jv_portfolio(h.drop(columns="subsidiary"))
    assert not drop2.any()


def test_cash_rule_keeps_money_market_labelled_short_term_investment():
    # Cash-equivalent lines are dropped; a money-market fund the filer lists
    # as a short-term investment is part of its portfolio and is kept.
    h = pd.DataFrame({
        "adsh": ["A", "A"],
        "identifier": ["Other Cash and Cash Equivalents",
                       "Short-Term Investments Fidelity Money Market Government Portfolio"],
        "source_rows": ["1", "2"]})
    drop, _ = clean.rule_cash(h)
    assert drop.tolist() == [True, False], drop.tolist()


def test_issuer_subtotal_rule_drops_only_true_subtotals():
    # "Ivy Hill" equals the sum of its two holdings: a subtotal, dropped.
    # "Acme Partners One" is a sibling tranche, so "Acme Partners" is kept.
    # "Beta Corp" does not equal its child's value, so it is kept.
    # The tolerance is 0.2%: "Gamma Inc" is 2% above its child (kept) and
    # "Delta LP" is 0.1% above its child, a rounding difference (dropped).
    h = pd.DataFrame({
        "adsh": ["A"] * 11, "ddate": ["2026-03-31"] * 11,
        "identifier": ["Ivy Hill", "Ivy Hill, Member interest",
                       "Ivy Hill, Subordinated loan", "Acme Partners",
                       "Acme Partners One", "Beta Corp", "Beta Corp, Term loan",
                       "Gamma Inc", "Gamma Inc, Term loan",
                       "Delta LP", "Delta LP, Term loan"],
        "fair_value": [300.0, 200.0, 100.0, 50.0, 50.0, 70.0, 60.0,
                       102.0, 100.0, 1001.0, 1000.0],
        "source_rows": [str(i) for i in range(11)]})
    drop, _ = clean.rule_issuer_subtotals(h)
    assert drop.tolist() == [True, False, False, False, False, False, False,
                             False, False, True, False], drop.tolist()


def test_rollforward_copy_rule_drops_only_bare_twins():
    # "Wittur Holding GmbH 1" repeats the schedule line's fair value with no
    # cost or principal: a roll-forward copy, dropped. A bare line with a
    # different value, and a bare negative line, are kept.
    h = pd.DataFrame({
        "adsh": ["A"] * 5, "ddate": ["2026-03-31"] * 5,
        "identifier": ["Wittur Holding GmbH | Capital Goods 1", "Wittur Holding GmbH 1",
                       "Acme LLC | Software 1", "Acme LLC 1", "Beta Inc 1"],
        "fair_value": [65.9e6, 65.9e6, 10e6, 9e6, -1e6],
        "cost": [63.5e6, None, 9e6, None, None],
        "principal": [58.7e6, None, 10e6, None, None],
        "source_rows": [str(i) for i in range(5)]})
    drop, _ = clean.rule_rollforward_copies(h)
    assert drop.tolist() == [False, True, False, False, False], drop.tolist()


def test_total_rule_spares_companies_named_total():
    # Real borrowers named "Total ..." carry a company suffix or a maturity
    # date; true totals carry neither.
    h = pd.DataFrame({
        "identifier": ["Total Investments at Fair Value", "Total Equity",
                       "Total Expert, Inc. | Growth Capital Loan",
                       "Total Access Elevator, LLC  Term Debt",
                       "PAI Pharma Total Investments First Lien - Revolver Maturity Date 02/13/32"],
        "adsh": ["x"] * 5, "source_rows": [str(i) for i in range(5)]})
    drop, _ = clean.rule_totals(h)
    assert drop.tolist() == [True, True, False, False, False], drop.tolist()


def test_debt_flag_marks_equity_and_warrants_without_dropping_them():
    # Equity, preferred units and warrants stay in the panel, flagged False.
    h = pd.DataFrame({
        "identifier": ["Acme Corp | First lien term loan", "Acme Corp | Common Stock",
                       "Beta LLC | Warrants", "Gamma Inc | Preferred Units"],
        "investment_type": [None, "Equity", None, None],
        "principal": [10.0, None, None, None], "spread": [None, None, None, None],
        "fair_value": [9.0, 3.0, 0.5, 2.0]})
    out = clean.flag_debt(h)
    assert len(out) == len(h)
    assert out["is_debt"].tolist() == [True, False, False, False], out["is_debt"].tolist()


# Regression tests from Lokesh's review of PR #3.

def test_rollforward_rule_keeps_a_distinct_instrument_with_the_same_value():
    # A loan (with cost and principal) and a separate preferred-equity holding
    # of the same issuer, both worth 100: the equity is not a copy of the loan.
    h = pd.DataFrame({
        "adsh": ["A", "A"], "ddate": ["2026-03-31"] * 2,
        "identifier": ["Acme, Inc. | First lien loan", "Acme, Inc. | Preferred equity"],
        "fair_value": [100.0, 100.0], "cost": [98.0, None], "principal": [100.0, None],
        "source_rows": ["0", "1"]})
    drop, _ = clean.rule_rollforward_copies(h)
    assert drop.tolist() == [False, False], drop.tolist()


def test_rollforward_rule_ignores_a_counterpart_already_dropped_as_jv():
    # The only full counterpart is a JV loan that rule_jv_portfolio drops first,
    # so the BDC's own bare holding must survive apply_rules.
    h = pd.DataFrame({
        "adsh": ["A", "A"], "ddate": ["2026-03-31"] * 2,
        "identifier": ["Acme, Inc. | First lien loan", "Acme, Inc. | First lien loan"],
        "subsidiary": ["Senior Loan Program [Member]", None],
        "fair_value": [100.0, 100.0], "cost": [98.0, None], "principal": [100.0, None],
        "source_rows": ["0", "1"]})
    kept, log = clean.apply_rules(h, [clean.rule_jv_portfolio, clean.rule_rollforward_copies])
    assert kept["source_rows"].tolist() == ["1"], kept["source_rows"].tolist()
    assert log["rows_affected"].tolist() == [1, 0]


def test_rollforward_rule_lets_one_holding_vouch_for_one_copy():
    # One schedule holding cannot make two bare rows into copies.
    h = pd.DataFrame({
        "adsh": ["A"] * 3, "ddate": ["2026-03-31"] * 3,
        "identifier": ["Acme, Inc. | Secured debt 1", "Acme, Inc. | Secured debt 1.1",
                       "Acme, Inc. | Secured debt 1.2"],
        "fair_value": [100.0, 100.0, 100.0], "cost": [98.0, None, None],
        "principal": [100.0, None, None], "source_rows": ["0", "1", "2"]})
    drop, _ = clean.rule_rollforward_copies(h)
    assert drop.tolist() == [False, True, False], drop.tolist()


def test_issuer_subtotal_rule_needs_a_real_name_boundary():
    # "ABC" is not the start of "ABCD LLC"; "ABC" and "ABC, LLC" differ only by a
    # company suffix. Equal values alone do not make a subtotal.
    h = pd.DataFrame({
        "adsh": ["A"] * 4, "ddate": ["2026-03-31"] * 4,
        "identifier": ["ABC", "ABCD LLC", "XYZ", "XYZ, LLC"],
        "fair_value": [100.0, 100.0, 50.0, 50.0],
        "source_rows": [str(i) for i in range(4)]})
    drop, _ = clean.rule_issuer_subtotals(h)
    assert drop.tolist() == [False, False, False, False], drop.tolist()


def test_issuer_subtotal_rule_keeps_a_parent_that_names_an_instrument():
    # Two distinct instruments with equal values: the first names a specific
    # loan, so it is a holding, not an issuer subtotal of the second.
    h = pd.DataFrame({
        "adsh": ["A", "A"], "ddate": ["2026-03-31"] * 2,
        "identifier": ["Acme, Inc. | First lien loan",
                       "Acme, Inc. | First lien loan, delayed draw"],
        "fair_value": [100.0, 100.0], "source_rows": ["0", "1"]})
    drop, _ = clean.rule_issuer_subtotals(h)
    assert drop.tolist() == [False, False], drop.tolist()
