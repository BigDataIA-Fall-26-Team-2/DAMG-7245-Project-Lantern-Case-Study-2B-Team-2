"""Instructor smoke test on a REAL release (needs network). Run before class, from the kit folder:

    python tools/smoke_real.py 2026_08 "Your Name you@northeastern.edu"

Downloads the release into data/raw/ if needed, runs the baseline pipeline stage by stage, and reports
what it found, so you know the notebooks will work on real data. It does not change params.yaml.
"""
import sys, time, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import acquire, clean, holdings, load, mapping, reconcile  # noqa: E402

release, ua = sys.argv[1], sys.argv[2]
raw = ROOT / "data" / "raw"; rdir = raw / f"{release}_bdc"
def stage(name, fn):
    t = time.perf_counter()
    try:
        out = fn(); print(f"  OK    {name}  ({time.perf_counter() - t:.1f} s)"); return out
    except Exception:
        print(f"  FAIL  {name}"); traceback.print_exc(); sys.exit(1)

z = raw / f"{release}_bdc.zip"
if not z.exists():
    stage("download " + acquire.release_url(release), lambda: acquire.download_release(release, raw, ua))
if not (rdir / "soi.tsv").exists():
    stage("unzip into " + str(rdir.relative_to(ROOT)), lambda: acquire.unzip_release(z, raw, release))
sub = stage("load SUB", lambda: load.load_sub(rdir)); tag = stage("load TAG", lambda: load.load_tag(rdir))
header = load.soi_header(rdir)
cm = mapping.map_soi_columns(header, tag)
print(f"        SOI has {len(header)} columns; mapped: {sorted(cm)}; UNMAPPED: {sorted(set(mapping.CANONICAL) - set(cm)) or 'none'}")
soi = stage("load SOI (mapped columns only)", lambda: load.load_soi(rdir, mapping.soi_usecols(header, cm)))
num = stage("load NUM (chunked: fair value + custom fair-value tags)",
            lambda: load.load_num(rdir, tags=[reconcile.FV_TAG], custom_fv=True))
print(f"        {len(sub)} current filings, {len(soi):,} SOI rows, {len(num):,} NUM facts kept")
soi = soi[soi["adsh"].isin(sub["adsh"])]
canon = stage("canonical frame, current period from SUB", lambda: holdings.split_periods(mapping.to_canonical(soi, cm), sub))
print(f"        dates parsed: {canon['ddate'].notna().mean():.0%} of rows; current rows {int(canon['is_current'].sum()):,}; "
      f"current rows without identifier {int((canon['is_current'] & canon['identifier'].isna()).sum()):,}")
h = stage("coalesce holdings", lambda: holdings.coalesce_holdings(canon)); cur = h[h["is_current"]]
print(f"        {len(cur):,} current holdings; median rows per holding {cur['n_rows'].median():.0f}; with conflicts {int((cur['n_conflicts'] > 0).sum())}")
kept, log = stage("baseline rules", lambda: clean.apply_rules(cur, [clean.rule_totals, clean.rule_cash]))
rec = stage("reconcile (every filing with SOI rows counts)",
            lambda: reconcile.reconcile(kept, reconcile.filed_totals(num, sub), sub, 0.01, soi_adsh=set(soi["adsh"])))
c = reconcile.coverage(rec, sub)
print(f"        baseline coverage: {c['filings_admitted']}/{c['filings_attempted']} filings ({c['share_of_filings']:.0%}), "
      f"{c['share_of_dollars']:.0%} of filed fair value; filings with no filed total: {int(rec['filed_fv'].isna().sum())}; "
      f"with no identifiable holdings: {int((rec['n_holdings'] == 0).sum())}; current filings without SOI rows: {c['filings_without_soi_rows']}")
show = rec.assign(gap=rec["gap_pct"].map(lambda x: "n/a" if x != x else f"{x:+.1%}"))
print(show[["name", "n_holdings", "gap", "admitted"]].head(15).to_string(index=False))
print("Smoke test complete: the notebooks' pipeline runs on", release)
