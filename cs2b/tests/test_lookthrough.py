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
    assert list(B["log"]["rows_affected"]) == [1, 1]


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
