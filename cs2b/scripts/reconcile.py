"""Stage 4 (reconcile): Part 3.

Compares each filing's cleaned holdings with its filed total (the
undimensioned InvestmentOwnedAtFairValue fact in NUM) and admits filings
within reconcile.tolerance from params.yaml. Also diagnoses failures.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import paths, reconcile

P = paths.load_params(ROOT)
work = ROOT / "outputs" / "work"
tolerance = P["reconcile"]["tolerance"]

kept = pd.read_parquet(work / "kept.parquet")
sub = pd.read_parquet(work / "sub.parquet")
num = pd.read_parquet(work / "num.parquet")
canon = pd.read_parquet(work / "canon.parquet")

filed = reconcile.filed_totals(num, sub)
rec = reconcile.reconcile(kept, filed, sub, tolerance,
                          soi_adsh=set(canon["adsh"]))
diag = reconcile.diagnose(rec, kept, num, canon)

rec.to_parquet(work / "rec.parquet", index=False)
diag.to_parquet(work / "diag.parquet", index=False)

admitted = int(rec["admitted"].fillna(False).astype(bool).sum()) if "admitted" in rec else "?"
print(f"reconcile: tolerance {tolerance}, {len(rec)} filings attempted, {admitted} admitted")