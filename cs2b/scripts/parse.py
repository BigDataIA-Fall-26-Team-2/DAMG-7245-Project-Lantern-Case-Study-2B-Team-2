"""Stage 2 (parse): Part 1.

Load every release listed in params.yaml, split current from comparative rows,
and coalesce one row per holding. No cleaning happens here. Writes the
intermediate tables the later stages read, under outputs/work/.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import combine, holdings, paths, reconcile

P = paths.load_params(ROOT)
work = ROOT / "outputs" / "work"
work.mkdir(parents=True, exist_ok=True)

dirs = paths.release_dirs(P, ROOT)
inputs = combine.load_inputs(dirs, num_tags=[reconcile.FV_TAG], custom_fv=True)
sub, num = inputs["sub"], inputs["num"]
canon = holdings.split_periods(inputs["canon"], sub)
h = holdings.coalesce_holdings(canon)

sub.to_parquet(work / "sub.parquet", index=False)
num.to_parquet(work / "num.parquet", index=False)
canon.to_parquet(work / "canon.parquet", index=False)
h.to_parquet(work / "holdings.parquet", index=False)

print(f"parse: {len(sub)} filings, {len(canon)} rows, "
      f"{int(canon['is_current'].sum())} current, {len(h)} holdings")