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
    # The pipeline runs clean.RULES; the four Part 2 rules find nothing in
    # the fixture (no commitment rows, JV rows, issuer subtotals or roll-forward copies).
    assert list(B["log"]["rule"]) == [r.__name__ for r in clean.RULES]
    assert list(B["log"]["rows_affected"]) == [0, 1, 1, 0, 0, 0, 0]


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
    if triage:  # synthetic reviewed evidence is an input, never a hand-edited report
        entries = []
        for row in B["rec"].loc[~B["rec"]["admitted"]].itertuples():
            category = next(value for name, value in TRIAGED.items() if name in row.name)
            entries.append({"adsh": row.adsh, "triage_category": category,
                            "evidence": "Synthetic fixture evidence", "example": "Synthetic SOI example",
                            "fix_or_reason": "Intentionally unresolved fixture case", "review_status": "reviewed",
                            "reviewed_holdings_fv": row.holdings_fv, "reviewed_filed_fv": row.filed_fv})
        pd.DataFrame(entries).to_csv(root / p["triage"]["input"], index=False)
    report.write_outputs(B["kept"], B["rec"], B["diag"], B["log"], root, p, sub=B["sub"])
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


def test_release_selection_is_explicit_and_fixture_is_isolated():
    p = {**P, "data": {**P["data"], "use_fixture": False},
         "release": "2026_05", "releases": ["2026_04", "2026_05"]}
    assert list(paths.release_dirs(p, ROOT)) == ["2026_04", "2026_05"]
    del p["releases"]
    assert list(paths.release_dirs(p, ROOT)) == ["2026_05"]
    for invalid in ([], "2026_05", ["2026_05", "2026_05"], ["../raw"], ["2026_13"]):
        p["releases"] = invalid
        try:
            paths.release_dirs(p, ROOT)
        except ValueError:
            continue
        raise AssertionError(f"Invalid selection accepted: {invalid}")
    p["data"]["use_fixture"] = True
    assert paths.release_dirs(p, ROOT) == {paths.FIXTURE_RELEASE: RDIR}


def test_combined_baseline_uses_one_copy_of_repeated_filings():
    with tempfile.TemporaryDirectory() as t:
        earlier, later = Path(t) / "earlier", Path(t) / "later"
        shutil.copytree(RDIR, earlier)
        shutil.copytree(RDIR, later)
        # A stale earlier copy must not contribute SOI values or NUM totals.
        for relative, columns in (("soi.tsv", [mapping.PRESET["fair_value"]]),
                                  ("datasets/num.tsv", ["value"])):
            frame = pd.read_csv(earlier / relative, sep="\t", dtype=str)
            for c in columns:
                frame[c] = pd.to_numeric(frame[c], errors="coerce") * 2
            frame.to_csv(earlier / relative, sep="\t", index=False)
        b = pipeline.run_baseline({"2026_04": earlier, "2026_05": later}, 0.01)
        single = pipeline.run_baseline(RDIR, 0.01)
        configured_single = pipeline.run_baseline({"2026_05": later}, 0.01)
        pd.testing.assert_frame_equal(configured_single["rec"], single["rec"])
        pd.testing.assert_frame_equal(b["rec"], single["rec"])
        assert set(b["kept"]["release"]) == {"2026_05"}
        assert set(b["num"]["release"]) == {"2026_05"}
        assert len(b["soi"]) == len(single["soi"])
        (later / "soi.tsv").unlink()
        try:
            pipeline.run_baseline({"2026_05": later}, 0.01)
        except FileNotFoundError as e:
            assert "soi.tsv" in str(e)
        else:
            raise AssertionError("Missing SOI must not silently shrink coverage")


def test_filed_totals_reject_conflicts_and_wrong_contexts():
    sub = pd.DataFrame({"adsh": ["same", "conflict", "context", "zero", "invalid"],
                        "period": ["2026-03-31"] * 5})
    facts = [
        ("same", 100, "USD", "0", "0", "2026-03-31"),
        ("same", 100, "USD", "0", "0", "2026-03-31"),
        ("conflict", 100, "USD", "0", "0", "2026-03-31"),
        ("conflict", 120, "USD", "0", "0", "2026-03-31"),
        ("context", 100, "USD", "0", "0", "2026-03-31"),
        ("context", 900, "EUR", "0", "0", "2026-03-31"),
        ("context", 800, "USD", "1", "0", "2026-03-31"),
        ("context", 700, "USD", "0", "1", "2026-03-31"),
        ("context", 600, "USD", "0", "0", "2025-12-31"),
        ("zero", 0, "USD", "0", "0", "2026-03-31"),
        ("invalid", float("inf"), "USD", "0", "0", "2026-03-31"),
    ]
    num = pd.DataFrame(facts, columns=["adsh", "value", "uom", "qtrs", "dimn", "ddate"])
    num["tag"] = reconcile.FV_TAG
    totals = reconcile.filed_totals(num, sub).set_index("adsh")
    assert totals.loc["same", "filed_fv"] == 100
    assert totals.loc["same", "filed_total_candidates"] == 1
    assert totals.loc["context", "filed_fv"] == 100
    assert totals.loc["conflict", "filed_total_status"] == "conflicting"
    assert pd.isna(totals.loc["conflict", "filed_fv"])
    assert totals.loc["zero", "filed_total_status"] == "nonpositive"
    assert totals.loc["invalid", "filed_total_status"] == "invalid"
    assert pd.isna(totals.loc["invalid", "filed_fv"])


def test_reconciliation_boundary_missing_values_and_coverage():
    ids = ["upper", "lower", "outside", "no_total", "zero", "negative",
           "all_missing", "partial", "infinite", "no_holdings", "no_soi"]
    sub = pd.DataFrame({"adsh": ids, "name": ids, "cik": ids,
                        "form": "10-Q", "period": "2026-03-31"})
    holdings = pd.DataFrame({
        "adsh": ids[:9] + ["partial"], "identifier": "loan",
        "fair_value": [101, 99, 101.001, 100, 0, -100, float("nan"), 100,
                       float("inf"), float("nan")]})
    filed = pd.DataFrame({"adsh": ids, "filed_fv": [100, 100, 100, float("nan"),
                          0, -100, 100, 100, 100, 100, 100]})
    rec = reconcile.reconcile(holdings, filed, sub, .01, soi_adsh=set(ids[:-1]))
    rows = rec.set_index("adsh")
    assert set(rows.index) == set(ids[:-1])
    assert set(rows.index[rows.admitted]) == {"upper", "lower", "partial"}
    assert rows.loc["outside", "gap_pct"] > .01
    assert rows.loc["no_holdings", "n_holdings"] == 0
    assert rows.loc["partial", "missing_fv"] == 1  # retain evidence; no invented zero
    assert pd.isna(rows.loc["all_missing", "holdings_fv"])
    for a in ("no_total", "zero", "negative", "all_missing", "infinite", "no_holdings"):
        assert pd.isna(rows.loc[a, "gap_pct"]), a
    cov = reconcile.coverage(rec, sub)
    assert cov["filings_attempted"] == 10
    assert cov["filings_without_soi_rows"] == 1
    assert cov["filings_without_soi_adsh"] == ["no_soi"]
    assert cov["filings_without_usable_filed_total"] == 3
    assert cov["filed_fv_attempted"] == 700
    for tol in (-.01, float("nan"), float("inf"), 1):
        try:
            reconcile.reconcile(holdings, filed, sub, tol)
        except ValueError:
            continue
        raise AssertionError(f"Invalid tolerance accepted: {tol}")
    empty = reconcile.reconcile(holdings.iloc[:0], filed, sub, .01, soi_adsh=set())
    assert empty.empty
    assert reconcile.coverage(empty, sub)["filings_without_soi_rows"] == len(sub)


def test_reports_preserve_triage_and_flag_changed_totals():
    import json
    p = {**P, "data": {**P["data"], "use_fixture": True}}
    b = pipeline.run_baseline({paths.FIXTURE_RELEASE: RDIR}, .01)
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        source = root / p["triage"]["input"]
        source.parent.mkdir(parents=True)
        entries = []
        for row in b["rec"].loc[~b["rec"]["admitted"]].itertuples():
            name = next(n for n in TRIAGED if n in row.name)
            entries.append({"adsh": row.adsh, "triage_category": TRIAGED[name],
                            "evidence": "Synthetic fixture evidence for " + row.adsh,
                            "example": "Synthetic SOI example for " + row.adsh,
                            "fix_or_reason": "Fixture intentionally retains this unresolved artifact",
                            "review_status": "reviewed", "reviewed_holdings_fv": row.holdings_fv,
                            "reviewed_filed_fv": row.filed_fv})
        pd.DataFrame(entries).to_csv(source, index=False)
        original = source.read_bytes()
        for _ in range(2):
            report.write_outputs(b["kept"], b["rec"], b["diag"], b["log"], root, p, sub=b["sub"])
            assert source.read_bytes() == original
        metrics = json.loads((root / "reports/coverage.json").read_text())
        assert metrics["triage_complete"] and metrics["triage_incomplete_filings"] == 0
        assert "preliminary" not in (root / "reports/coverage.md").read_text()
        assert "Triage review complete" in (root / "reports/coverage.md").read_text()
        cov = pd.read_csv(root / "reports/coverage.csv", keep_default_na=False)
        assert list(cov.columns) == report.COVERAGE_COLS
        assert cov.loc[cov.admitted, "triage_category"].eq("").all()
        panel = pd.read_parquet(root / "outputs/panel/holdings.parquet")
        assert set(panel.adsh) == set(cov.loc[cov.admitted, "adsh"])
        assert set(panel.release) == {paths.FIXTURE_RELEASE}
        assert panel.is_debt.dtype == bool
        assert "rf_opening" in b["holdings"]
        sums = panel.groupby("adsh").fair_value.sum()
        for row in cov[cov.admitted].itertuples():
            assert abs(sums[row.adsh] - float(row.holdings_fv)) < .01
        assert "Synthetic fixture evidence" in (root / "reports/triage.md").read_text()
        changed = b["rec"].copy()
        target = entries[0]["adsh"]
        changed.loc[changed.adsh.eq(target), "holdings_fv"] += 10
        report.write_outputs(b["kept"], changed, b["diag"], b["log"], root, p, sub=b["sub"])
        metrics = json.loads((root / "reports/coverage.json").read_text())
        assert metrics["triage_incomplete_adsh"] == [target]
        assert "Outputs are preliminary" in (root / "reports/coverage.md").read_text()
        assert "totals changed; re-review required" in (root / "reports/triage.md").read_text()
        assert source.read_bytes() == original


def test_reports_handle_unreviewed_triage_and_empty_panel():
    import json
    p = {**P, "data": {**P["data"], "use_fixture": True}}
    b = pipeline.run_baseline({paths.FIXTURE_RELEASE: RDIR}, .01)
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        rec = b["rec"].copy()
        rec["admitted"] = False
        report.write_outputs(b["kept"], rec, b["diag"], b["log"], root, p, sub=b["sub"])
        assert pd.read_parquet(root / "outputs/panel/holdings.parquet").empty
        metrics = json.loads((root / "reports/coverage.json").read_text())
        assert metrics["triage_incomplete_filings"] == len(rec)
        assert metrics["filings_admitted"] == 0
        tri = (root / "reports/triage.md").read_text()
        assert tri.count("## ") == len(rec)  # even when diagnostics omit a filing
        source = root / p["triage"]["input"]
        source.parent.mkdir(parents=True)
        entry = {c: "" for c in report.TRIAGE_COLS}
        entry.update(adsh=rec.adsh.iloc[0], triage_category="other", evidence="Draft evidence")
        pd.DataFrame([entry]).to_csv(source, index=False)
        report.write_outputs(b["kept"], rec, b["diag"], b["log"], root, p, sub=b["sub"])
        cov = pd.read_csv(root / "reports/coverage.csv")
        assert cov.triage_category.eq("to_triage").all()
        assert "Draft evidence" in (root / "reports/triage.md").read_text()
        for bad_rows in ([{**entry, "triage_category": "invented_category"}], [entry, entry]):
            pd.DataFrame(bad_rows).to_csv(source, index=False)
            try:
                report.write_outputs(b["kept"], rec, b["diag"], b["log"], root, p, sub=b["sub"])
            except ValueError:
                continue
            raise AssertionError("Malformed triage must fail, not silently replace reports")


def test_reports_reject_panel_mismatch_or_missing_provenance():
    p = {**P, "data": {**P["data"], "use_fixture": True}}
    b = pipeline.run_baseline({paths.FIXTURE_RELEASE: RDIR}, .01)
    admitted = set(b["rec"].loc[b["rec"].admitted, "adsh"])
    index = b["kept"].index[b["kept"].adsh.isin(admitted)][0]
    with tempfile.TemporaryDirectory() as t:
        for column, value in (("fair_value", 1e15), ("source_rows", ""),
                              ("release", ""), ("is_current", False)):
            kept = b["kept"].copy()
            kept.loc[index, column] = value
            try:
                report.write_outputs(kept, b["rec"], b["diag"], b["log"], Path(t), p, sub=b["sub"])
            except ValueError:
                continue
            raise AssertionError(f"Invalid panel accepted: {column}")


def test_configured_rules_preserve_order_and_reject_unavailable_names():
    assert pipeline.configured_rules({}) == clean.RULES
    assert pipeline.configured_rules({"cleaning": {"rules": ["rule_cash", "rule_totals"]}}) == [clean.rule_cash, clean.rule_totals]
    for names in ([], "rule_cash", ["rule_cash", "rule_cash"],
                  ["rule_not_implemented"], ["apply_rules"], [None]):
        try:
            pipeline.configured_rules({"cleaning": {"rules": names}})
        except ValueError:
            continue
        raise AssertionError(f"Invalid rule selection accepted: {names}")


def test_checker_uses_release_and_row_together():
    import yaml
    with tempfile.TemporaryDirectory() as t:
        root = _outputs_in_temp_repo(t)
        p = paths.load_params(root)
        p["data"]["use_fixture"] = False
        p["releases"] = ["2026_04", "2026_05"]
        for release in p["releases"]:
            shutil.copytree(RDIR, root / "data/raw" / f"{release}_bdc")
        (root / "params.yaml").write_text(yaml.safe_dump(p))
        b = pipeline.run_baseline(paths.release_dirs(p, root), .01)
        report.write_outputs(b["kept"], b["rec"], b["diag"], b["log"], root, p, sub=b["sub"])
        assert all(ok for _, ok, _ in check.run_checks(root, sample=1000))
        output = root / "outputs/panel/holdings.parquet"
        original = pd.read_parquet(output)
        assert set(original.release) == {"2026_05"}
        wrong = original.copy()
        wrong["release"] = "2026_04"  # same row numbers, but an unselected filing copy
        wrong.to_parquet(output, index=False)
        result = check.run_checks(root, sample=1000)
        assert not result[-1][1], result
        original.drop(columns="release").to_parquet(output, index=False)
        assert not check.run_checks(root)[0][1]


def test_checker_rejects_missing_totals_and_gap_tampering():
    with tempfile.TemporaryDirectory() as t:
        root = _outputs_in_temp_repo(t)
        output = root / "reports/coverage.csv"
        original = pd.read_csv(output, dtype={"adsh": str})
        for field, expected_failure in (("filed_fv", "filed totals match NUM"),
                                        ("gap_pct", "gap_pct is computed correctly")):
            altered = original.copy()
            altered.loc[altered.admitted, field] = float("nan")
            altered.to_csv(output, index=False)
            failed = [name for name, ok, _ in check.run_checks(root) if not ok]
            assert expected_failure in failed, failed
        duplicate = pd.concat([original, original.iloc[[0]]], ignore_index=True)
        duplicate.to_csv(output, index=False)
        assert not check.run_checks(root)[2][1]
        original.to_csv(output, index=False)
        # An allowed category alone is insufficient evidence for completed triage.
        (root / P["triage"]["input"]).unlink()
        failed = [name for name, ok, _ in check.run_checks(root) if not ok]
        assert failed == ["every excluded filing has a valid triage_category"], failed
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
        "rf_opening": [False, True, False, True, True],
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


def test_total_rule_handles_net_assets_and_spaced_subtotals_conservatively():
    # NexPoint's bare Net Assets and Saratoga's spaced Sub Total are
    # summaries. Similar issuer names and instrument labels must survive.
    labels = ["Net Assets", "  NET ASSETS  ",
              "Sub Total Non-control/Non-affiliate investments",
              "Sub\tTotal First Lien", "Subtotal First Lien",
              "Net Assets Capital", "Net Assets, LLC | First lien loan",
              "Investment | Net Assets", "Net Assets | Common stock",
              "Sub Total Holdings, Inc. | Loan",
              "Sub Total First Lien Maturity Date 02/13/32", None]
    drop, _ = clean.rule_totals(pd.DataFrame({"identifier": labels}))
    assert drop.tolist() == [True] * 5 + [False] * 7, drop.tolist()


def test_category_summaries_keep_instruments_and_unknown_classifications():
    root = "Non-controlled/Non-Affiliated Investments -215.2% of Shareholder's Equity"
    sector = root + " - Investments made in Austria - Capital Equipment"
    labels = [root, root + " - Investments made in Austria", sector,
              sector + " - Example GmbH - First Lien - Term Loan",
              "Investments - non-controlled/non-affiliated - First Lien Senior Secured Loan - Software",
              "Software Preferred Equity Securities Controlled Investments",
              "Example Software Preferred Equity Securities Controlled Investments",
              root + " - Investments made in Austria - Unrecognized Sector",
              "Acme | Controlled Investments", "Controlled Investments, LLC",
              "Controlled Investments | Term Loan", "Controlled Investments"]
    h = pd.DataFrame({"identifier": labels, "maturity": [None] * 11 + ["2030-01-01"]})
    drop, _ = clean.rule_totals(h)
    assert drop.tolist() == [True, True, True, False, True, True] + [False] * 6
    # Even recognized category text is retained when instrument terms or
    # conflicting coalesced values make its interpretation ambiguous.
    for col, value in [("principal", 100), ("interest_rate", .1), ("spread", .05),
                       ("pik_rate", .02), ("n_conflicts", 1)]:
        assert not clean.rule_totals(pd.DataFrame({"identifier": [sector], col: [value]}))[0].any()


def test_nested_classifications_are_removed_without_using_filed_totals():
    for root, middle, leaf_prefix in [
        ("Non-controlled/Non-Affiliated Investments", "Investments made in Canada",
         "Capital Equipment"),
        ("Investments - non-controlled/non-affiliated", "First Lien Senior Secured Loan",
         "Software"),
    ]:
        labels = [root, root + " - " + middle, root + " - " + middle + " - " + leaf_prefix]
        labels += [labels[-1] + " - Example LLC - Term Loan",
                   labels[-1] + " - Example LLC - Revolver"]
        h = pd.DataFrame({"identifier": labels, "fair_value": [100, 100, 100, 40, 60]})
        dropped, _ = clean.rule_totals(h)
        assert dropped.tolist() == [True, True, True, False, False]
        assert h.loc[~dropped, "fair_value"].sum() == 100


def test_short_category_summary_requires_a_context_matched_instrument():
    h = pd.DataFrame({
        "adsh": ["A", "A"], "ddate": ["2026-03-31"] * 2,
        "release": ["2026_05"] * 2, "subsidiary": [None, None],
        "identifier": ["Aerospace & Defense First Lien Senior Secured Term Loan",
                       "Example Holdings First Lien Senior Secured Term Loan Due 9/1/2030"],
        "cost": [90., 90.], "fair_value": [100., 100.],
        "maturity": [None, "2030-09-01"], "n_conflicts": [0, 0]})
    assert clean.rule_totals(h)[0].tolist() == [True, False]
    for col, value in [("adsh", "B"), ("ddate", "2025-12-31"), ("release", "2026_04"),
                       ("subsidiary", "JV"), ("cost", 89.), ("fair_value", 101.),
                       ("maturity", None), ("n_conflicts", 1)]:
        changed = h.copy()
        changed.loc[1, col] = value
        assert not clean.rule_totals(changed)[0].any(), col
    assert not clean.rule_totals(h.iloc[:1])[0].any()
    empty_header = h.iloc[:1].copy()
    empty_header[["cost", "fair_value"]] = float("nan")
    assert clean.rule_totals(empty_header)[0].all()
    empty_header["identifier"] = "Example Holdings First Lien Senior Secured Term Loan"
    assert not clean.rule_totals(empty_header)[0].any()


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


def test_commitment_rule_drops_only_unfunded_commitment_rows():
    # Guna's spot-check finding: T Series SOI row 97935 is a row from the
    # unfunded-commitments table, not a holding. It names the commitment type
    # and expiration date and has no cost or principal: dropped. The funded
    # loan, a commitment-looking row that carries principal, and a row naming
    # only a commitment type are kept.
    h = pd.DataFrame({
        "adsh": ["A"] * 4, "ddate": ["2026-03-31"] * 4,
        "identifier": [
            "Investments First Lien Debt Cerity Partners, LLC Commitment Type Revolver Commitment Expiration Date 07/28/2031",
            "Cerity Partners, LLC | First Lien Term Loan",
            "Acme Commitment Type Delayed Draw Commitment Expiration Date 1/1/2027",
            "Investments Anaplan, Inc. Commitment Type Revolving Loan"],
        "fair_value": [None, 50.0, -1.0, -2.0], "cost": [None, 49.0, None, None],
        "principal": [None, 50.0, 5.0, None], "source_rows": ["0", "1", "2", "3"]})
    drop, _ = clean.rule_commitment_rows(h)
    assert drop.tolist() == [True, False, False, False], drop.tolist()


# Regression tests from Lokesh's review of PR #3.

def test_rollforward_rule_keeps_a_distinct_instrument_with_the_same_value():
    # A loan (with cost and principal) and a separate preferred-equity holding
    # of the same issuer, both worth 100: the equity is not a copy of the loan.
    h = pd.DataFrame({
        "adsh": ["A", "A"], "ddate": ["2026-03-31"] * 2,
        "identifier": ["Acme, Inc. | First lien loan", "Acme, Inc. | Preferred equity"],
        "fair_value": [100.0, 100.0], "cost": [98.0, None], "principal": [100.0, None],
        "rf_opening": [False, True], "source_rows": ["0", "1"]})
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
        "rf_opening": [False, True], "source_rows": ["0", "1"]})
    kept, log = clean.apply_rules(h, [clean.rule_jv_portfolio, clean.rule_rollforward_copies])
    assert kept["source_rows"].tolist() == ["1"], kept["source_rows"].tolist()
    assert log["rows_affected"].tolist() == [1, 0]
    # Also exercise sequential evaluation within ONE subsidiary. Cross-JV
    # isolation alone must not mask a regression in apply_rules ordering.
    same_context = h.assign(subsidiary=None)
    def remove_first(rows):
        return rows["source_rows"].eq("0"), "previous rule excluded counterpart"
    kept, log = clean.apply_rules(same_context, [remove_first, clean.rule_rollforward_copies])
    assert kept["source_rows"].tolist() == ["1"]
    assert log["rows_affected"].tolist() == [1, 0]


def test_rollforward_rule_lets_one_holding_vouch_for_one_copy():
    # One schedule holding cannot make two bare rows into copies.
    h = pd.DataFrame({
        "adsh": ["A"] * 3, "ddate": ["2026-03-31"] * 3,
        "identifier": ["Acme, Inc. | Secured debt 1", "Acme, Inc. | Secured debt 1.1",
                       "Acme, Inc. | Secured debt 1.2"],
        "fair_value": [100.0, 100.0, 100.0], "cost": [98.0, None, None],
        "principal": [100.0, None, None], "rf_opening": [False, True, True],
        "source_rows": ["0", "1", "2"]})
    drop, _ = clean.rule_rollforward_copies(h)
    assert drop.tolist() == [False, True, False], drop.tolist()


# Regression tests from Lokesh's second review of PR #3 (commit 6fd1844).

def test_rollforward_rule_keeps_a_revolver_that_matches_a_term_loan_by_value():
    # Lokesh's example: a term loan (with cost/principal) and a revolver
    # (without), same issuer, both 100. Both are debt, but nothing shows the
    # revolver is a roll-forward copy, so it is kept. Even with roll-forward
    # evidence it is kept, because a revolver is not a copy of a term loan.
    base = {"adsh": ["A", "A"], "ddate": ["2026-03-31"] * 2,
            "identifier": ["Acme | First lien term loan", "Acme | Revolving credit facility"],
            "fair_value": [100.0, 100.0], "cost": [98.0, None],
            "principal": [100.0, None], "source_rows": ["0", "1"]}
    no_evidence = pd.DataFrame({**base, "rf_opening": [False, False]})
    drop, _ = clean.rule_rollforward_copies(no_evidence)
    assert drop.tolist() == [False, False], drop.tolist()
    with_evidence = pd.DataFrame({**base, "rf_opening": [False, True]})
    drop, _ = clean.rule_rollforward_copies(with_evidence)
    assert drop.tolist() == [False, False], drop.tolist()
    without_column = pd.DataFrame(base)
    drop, _ = clean.rule_rollforward_copies(without_column)
    assert drop.tolist() == [False, False], drop.tolist()


def test_rollforward_evidence_is_an_opening_value_without_cost_or_principal():
    # The roll-forward copy "Acme | Secured Debt 1.1" has an opening value
    # (prior period, no cost or principal); the schedule line "Acme | Secured
    # Debt 1" has cost in both periods. Only the copy gets rf_opening, and the
    # rule then drops it.
    h = pd.DataFrame({
        "adsh": ["A"] * 4,
        "ddate": ["2026-03-31", "2025-12-31", "2026-03-31", "2025-12-31"],
        "is_current": [True, False, True, False],
        "identifier": ["Acme | Secured Debt 1", "Acme | Secured Debt 1",
                       "Acme | Secured Debt 1.1", "Acme | Secured Debt 1.1"],
        "fair_value": [100.0, 95.0, 100.0, 95.0], "cost": [98.0, 97.0, None, None],
        "principal": [100.0, 100.0, None, None], "source_rows": ["0", "1", "2", "3"]})
    out = clean.add_rollforward_evidence(h)
    assert out["rf_opening"].tolist() == [False, False, True, False], out["rf_opening"].tolist()
    cur = out[out["is_current"]]
    drop, _ = clean.rule_rollforward_copies(cur)
    assert drop.tolist() == [False, True], drop.tolist()
    # The same bare row without an opening value has no roll-forward
    # evidence: it could be a separate holding, so it is kept.
    drop, _ = clean.rule_rollforward_copies(cur.assign(rf_opening=False))
    assert drop.tolist() == [False, False], drop.tolist()


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


def test_coinvestment_summary_requires_complete_label_and_no_instrument_terms():
    h = pd.DataFrame({
        "identifier": ["Co-investment", "Co-investments", "Co-investment LLC",
                       "Co-investment Fund interest", "Co-investment", "Co-investment"],
        "cost": [90.] * 6, "fair_value": [100.] * 6,
        "principal": [None, None, None, None, 100., None],
        "n_conflicts": [0, 0, 0, 0, 0, 1]})
    drop, _ = clean.rule_totals(h)
    assert drop.tolist() == [True, True, False, False, False, False]


def test_rollforward_classification_prefixes_preserve_context_and_tranches():
    pair = pd.DataFrame({
        "adsh": ["A"] * 2, "ddate": ["2026-03-31"] * 2,
        "release": ["2026_05"] * 2, "subsidiary": [None] * 2,
        "identifier": [
            "Debt Investments, First Lien Senior Secured, Example Holdings, LLC - Delayed Draw Term Loan First-Out",
            "Non-controlled, Affiliated investments, Example Holdings, LLC - Delayed Draw Loan First-Out"],
        "fair_value": [100., 100.], "cost": [95., None],
        "principal": [100., None], "rf_opening": [False, True]})
    assert clean.rule_rollforward_copies(pair)[0].tolist() == [False, True]
    for col, value in [("adsh", "B"), ("ddate", "2026-06-30"),
                       ("release", "2026_06"), ("subsidiary", "JV"),
                       ("rf_opening", False), ("fair_value", 101.)]:
        changed = pair.copy(); changed.loc[1, col] = value
        assert not clean.rule_rollforward_copies(changed)[0].any(), col
    for label in [pair.loc[1, "identifier"].replace("First-Out", "Last-Out"),
                  pair.loc[1, "identifier"].replace("Example", "Different"),
                  pair.loc[1, "identifier"].replace("Delayed Draw Loan", "Revolver")]:
        changed = pair.copy(); changed.loc[1, "identifier"] = label
        assert not clean.rule_rollforward_copies(changed)[0].any(), label
    equity = pair.copy()
    equity["identifier"] = [
        "Control Investments Equity Investments Multi-Sector Holdings Example I LLC Investment Type Equity 50% Equity Interest",
        "Control Investments Equity Investments Example I LLC"]
    equity["principal"] = None
    assert clean.rule_rollforward_copies(equity)[0].tolist() == [False, True]


def test_source_evidence_checks_snapshot_context_value_and_scope():
    import hashlib
    import json
    from lookthrough import evidence
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = '''<xbrli:context id="c"><xbrli:entity><xbrli:identifier scheme="sec">123</xbrli:identifier>
        <xbrli:segment><xbrldi:typedMember dimension="us-gaap:InvestmentIdentifierAxis"><value>Example LLC</value></xbrldi:typedMember></xbrli:segment>
        </xbrli:entity><xbrli:period><xbrli:instant>2026-03-31</xbrli:instant></xbrli:period></xbrli:context>
        <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
        <ix:nonFraction id="f" contextRef="c" unitRef="usd" name="us-gaap:InvestmentOwnedAtFairValue"
        scale="3" decimals="-3" format="ixt:num-dot-decimal">10</ix:nonFraction>'''
        doc = root / 'filing.html'; doc.write_text(source)
        fact = dict(adsh='A', release='2026_05', period='2026-03-31', identifier='Example LLC',
                    subsidiary=None, fact_id='f', role='schedule', instrument_key='loan',
                    scope='investment', basis='Source-checked primary schedule position')
        data = dict(version=1, documents={'A': dict(file=doc.name,
                    sha256=hashlib.sha256(doc.read_bytes()).hexdigest(), url='https://example.test/filing')}, facts=[fact])
        manifest = root / 'evidence.json'; manifest.write_text(json.dumps(data))
        c = pd.DataFrame(dict(adsh=['A'], release=['2026_05'], period=['2026-03-31'],
                             ddate=['2026-03-31'], identifier=['Example LLC'], cik=['123'],
                             subsidiary=[None], fair_value=[10000.]))
        out = evidence.attach(c, manifest, root)
        assert out.source_role.tolist() == ['schedule'] and out.source_decimals.tolist() == [-3]
        def rejected(frame=c):
            try:
                evidence.attach(frame, manifest, root)
            except ValueError:
                return
            raise AssertionError('Invalid source evidence was accepted')
        rejected(c.assign(fair_value=9999.))
        rejected(c.assign(cik='456'))
        rejected(c.assign(identifier='Different loan'))
        rejected(c.assign(subsidiary='JV'))
        doc.write_text(source + 'changed'); rejected(); doc.write_text(source)
        data['facts'] = [fact, fact]; manifest.write_text(json.dumps(data)); rejected()
        data['facts'] = [dict(fact, role='guess')]; manifest.write_text(json.dumps(data)); rejected()
        data['facts'] = [fact]; manifest.write_text(json.dumps(data))
        changed = source.replace('2026-03-31', '2025-12-31'); doc.write_text(changed)
        data['documents']['A']['sha256'] = hashlib.sha256(doc.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(data)); rejected()
        # An annotation from a different release is not silently reused, even
        # for an identical issuer and amount. It leaves the new row untouched.
        assert evidence.attach(c.assign(release='2026_06'), manifest, root).source_role.isna().all()
        assert paths.source_evidence_paths({'data': {'use_fixture': True},
            'source_evidence': {'input': 'missing', 'documents': 'missing'}}, root) == {}


def test_source_disclosures_require_unique_identity_scope_and_source_precision():
    h = pd.DataFrame({
        'adsh': ['A'] * 3, 'ddate': ['2026-03-31'] * 3, 'release': ['2026_05'] * 3,
        'subsidiary': [None] * 3, 'identifier': ['Example loan', 'Example note', 'Treasury fund'],
        'cost': [9000., None, 100.], 'principal': [10000., None, None],
        'fair_value': [10000., 10481., 100.], 'n_conflicts': [0] * 3,
        'source_role': ['schedule', 'rollforward_repeat', 'cash_equivalent'],
        'source_scope': ['investment', 'investment', 'outside_investment_total'],
        'source_instrument_key': ['loan', 'loan', 'cash'],
        'source_fact_id': ['f1', 'f2', 'f3'], 'source_decimals': [-3, 0, 0],
        'source_document_sha256': ['verified'] * 3})
    assert clean.rule_source_disclosures(h)[0].tolist() == [False, True, True]
    assert not clean.rule_source_disclosures(h.drop(columns='source_role'))[0].any()
    for col, value in [('fair_value', 10501.), ('fair_value', -1.),
                       ('source_decimals', None), ('source_fact_id', None),
                       ('source_fact_id', 'f1'), ('n_conflicts', 1),
                       ('source_instrument_key', 'different loan'), ('cost', 9000.),
                       ('source_scope', 'unknown'), ('source_document_sha256', 'different'),
                       ('adsh', 'B'), ('release', '2026_06'),
                       ('ddate', '2026-06-30'), ('subsidiary', 'JV')]:
        changed = h.copy(); changed.loc[1, col] = value
        assert not clean.rule_source_disclosures(changed)[0].iloc[1], (col, value)
    changed = h.copy(); changed.loc[0, 'source_decimals'] = 0
    assert not clean.rule_source_disclosures(changed)[0].iloc[1]
    changed = h.copy(); changed.loc[1, 'source_role'] = 'narrative_repeat'
    assert clean.rule_source_disclosures(changed)[0].iloc[1]
    ambiguous = pd.concat([h, h.iloc[[0]]], ignore_index=True)
    assert not clean.rule_source_disclosures(ambiguous)[0].iloc[1]
    changed = h.copy(); changed.loc[2, 'source_scope'] = 'investment'
    assert not clean.rule_source_disclosures(changed)[0].iloc[2]
    changed = h.copy(); changed.loc[2, 'identifier'] = 'Short-term investment treasury fund'
    assert not clean.rule_source_disclosures(changed)[0].iloc[2]


def test_triage_review_state_requires_current_totals_and_complete_evidence():
    entry = dict(review_status='reviewed', triage_category='other', evidence='filing',
                 example='row 1', fix_or_reason='unresolved',
                 reviewed_holdings_fv=120., reviewed_filed_fv=100.)
    assert report.triage_review_state(entry, 120., 100.) == (True, False)
    assert report.triage_review_state(entry, 130., 100.) == (False, True)
    assert report.triage_review_state({**entry, 'evidence': ''}, 120., 100.) == (False, False)
    assert report.triage_review_state(None, 120., 100.) == (False, False)
    assert report.triage_review_state({**entry, 'review_status': 'draft'}, 120., 100.) == (False, False)


def test_app_exports_evidence_and_marks_stale_triage_without_quoting_prices():
    import io
    from unittest.mock import patch
    sys.path.insert(0, str(ROOT))
    from app import engine
    result = pipeline.run_baseline(RDIR, .01)
    h = result['holdings'].copy()
    h['source_fact_id'] = 'fixture-fact'
    h['source_document_sha256'] = 'fixture-hash'
    sub = result['sub'].copy()
    sub['release'] = 'fixture'
    sub['inlineurl'] = 'https://example.org/filing'
    inp = dict(current=h[h.is_current], sub=sub,
               filed=reconcile.filed_totals(result['num'], sub),
               soi_adsh=set(result['canon'].adsh), read={})
    failed = result['rec'].loc[~result['rec'].admitted].iloc[0]
    entry = dict(adsh=failed.adsh, triage_category='other', evidence='old evidence',
                 example='row 1', fix_or_reason='old explanation', review_status='reviewed',
                 reviewed_holdings_fv=-123., reviewed_filed_fv=-123.)
    tri = pd.DataFrame([entry]).set_index('adsh')
    with patch.object(engine, '_prepare', return_value=inp), \
         patch.object(engine, 'available_releases', return_value=['fixture']), \
         patch.object(engine, '_triage', return_value=tri):
        run = engine.run(['fixture'])
    rid = run['run_id']
    try:
        rec = engine._runs[rid]['rec'].set_index('adsh')
        assert rec.loc[failed.adsh, 'triage_status'] == 'stale'
        assert rec.loc[failed.adsh, 'triage_category'] == 'to_triage'
        panel = pd.read_csv(io.StringIO(engine.panel_csv(rid)))
        assert panel.source_fact_id.eq('fixture-fact').all()
        loans = engine.loans(rid)
        assert all(row['price'] is None for row in loans['loans'])
        assert all(row['principal'] is None for row in loans['by_fund'])
        assert engine.loans(rid, price_hi=90)['count'] == 0
        assert 'source_document_sha256' in pd.read_csv(io.StringIO(engine.loans_csv(rid)))
    finally:
        engine._runs.pop(rid, None)


def test_app_raw_parse_passes_configured_source_evidence():
    from unittest.mock import patch
    sys.path.insert(0, str(ROOT))
    from app import engine
    inp = pipeline.run_baseline(RDIR, .01)
    inp['sub']['release'] = 'fixture'
    inp['canon']['release'] = 'fixture'
    evidence_paths = dict(source_manifest=Path('/fixture/evidence.json'),
                          source_documents=Path('/fixture/documents'))
    with patch.object(engine, '_inputs', {}), \
         patch.object(engine, 'release_dirs', return_value={'fixture': RDIR}), \
         patch.object(engine.paths, 'source_evidence_paths', return_value=evidence_paths), \
         patch.object(engine.combine, 'load_inputs', return_value=inp) as loader:
        engine._prepare(('fixture',))
        assert loader.call_args.kwargs['source_manifest'] == evidence_paths['source_manifest']
        assert loader.call_args.kwargs['source_documents'] == evidence_paths['source_documents']
def test_spot_sample_is_independent_of_input_order_and_fair_value_ties():
    import runpy
    sample = runpy.run_path(str(ROOT / 'scripts/spot_check_sample.py'))['select_sample']
    rows = [dict(adsh=f'A{i:02}', release='2026_05', identifier=f'loan {j}',
                 source_rows=str(i * 10 + j), fair_value=100.)
            for i in range(12) for j in range(4)]
    panel = pd.DataFrame(rows)
    first = sample(panel).reset_index(drop=True)
    second = sample(panel.sample(frac=1, random_state=123)).reset_index(drop=True)
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 20 and first.adsh.nunique() == 10
    assert first.groupby('adsh').size().eq(2).all()
    assert sample(panel.iloc[:0]).empty


def test_shared_sampling_zero_counts_and_configured_counts():
    from lookthrough.sampling import select_sample
    panel = pd.DataFrame([dict(adsh=f'A{i}', release='fixture', identifier=f'loan{j}',
                               source_rows=str(j), fair_value=float(j))
                          for i in range(4) for j in range(5)])
    assert select_sample(panel, n_largest=0, n_random=0).empty
    assert select_sample(panel, per_filing=0).empty
    result = select_sample(panel, n_largest=1, n_random=2, per_filing=3)
    assert len(result) == 9 and result.adsh.nunique() == 3
    from unittest.mock import patch
    sys.path.insert(0, str(ROOT))
    from app import engine
    app_panel = panel.assign(name="fixture", is_debt=True, principal=1., filing_url="fixture")
    rec = pd.DataFrame({"adsh": panel.adsh.unique(), "admitted": True})
    with patch.object(engine, '_get', return_value={"kept": app_panel, "rec": rec}):
        assert engine.sample('fixture', 0, 0) == []
        assert engine.sample('fixture') == engine.records(select_sample(app_panel)[engine.SAMPLE_COLS])
    pd.testing.assert_frame_equal(result, select_sample(panel.iloc[::-1], n_largest=1,
                                                       n_random=2, per_filing=3))


def test_notebook_scratch_cannot_overwrite_original_evidence():
    import runpy
    scratch_copy = runpy.run_path(str(ROOT / 'tools/run_notebooks.py'))['scratch_copy']
    with tempfile.TemporaryDirectory() as tmp:
        original = Path(tmp)
        (original / 'reports').mkdir()
        (original / 'params.yaml').write_text("release: 2026_05\nreleases: [2026_04, 2026_05]\n")
        evidence = original / 'reports/spot_check.csv'
        evidence.write_text('reviewed evidence')
        scratch = scratch_copy(original)
        try:
            (scratch / 'reports/spot_check.csv').write_text('blank template')
            assert evidence.read_text() == 'reviewed evidence'
            assert (scratch / '.notebook-scratch').exists()
        finally:
            shutil.rmtree(scratch.parent)
