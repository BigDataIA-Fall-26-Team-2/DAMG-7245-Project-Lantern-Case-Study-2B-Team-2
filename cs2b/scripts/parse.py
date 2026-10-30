"""Stage 2 (parse): Part 1.

Load every release listed in params.yaml, split current from comparative rows,
and coalesce one row per holding. No cleaning happens here. Writes the
intermediate tables the later stages read, under outputs/work/.

The dvc.yaml pipeline runs the real release only and needs an explicit
`releases` list, even for one release (for example releases: ["2026_05"]).
The single-release fallback `release` in paths.release_dirs is for notebooks
and tools; DVC requires every tracked parameter to exist.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import combine, holdings, paths, reconcile

P = paths.load_params(ROOT)
if P["data"].get("use_fixture"):
    sys.exit("parse: data.use_fixture is true. The dvc.yaml pipeline runs the "
             "real release only; set data.use_fixture: false.")
if not P.get("releases"):
    sys.exit('parse: the dvc.yaml pipeline needs a non-empty releases list, even '
             'for one release (for example releases: ["2026_05"]). The single '
             '`release` fallback is for notebooks and tools only.')

work = ROOT / "outputs" / "work"
work.mkdir(parents=True, exist_ok=True)

dirs = paths.release_dirs(P, ROOT)
inputs = combine.load_inputs(dirs, num_tags=[reconcile.FV_TAG], custom_fv=True,
                             **paths.source_evidence_paths(P, ROOT))
sub, num = inputs["sub"], inputs["num"]
canon = holdings.split_periods(inputs["canon"], sub)
h = holdings.coalesce_holdings(canon)

sub.to_parquet(work / "sub.parquet", index=False)
num.to_parquet(work / "num.parquet", index=False)
canon.to_parquet(work / "canon.parquet", index=False)
h.to_parquet(work / "holdings.parquet", index=False)

print(f"parse: {len(sub)} filings, {len(canon)} rows, "
      f"{int(canon['is_current'].sum())} current, {len(h)} holdings")
