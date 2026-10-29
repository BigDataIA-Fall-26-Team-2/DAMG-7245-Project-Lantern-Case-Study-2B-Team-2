"""Stage 3 (clean): Part 2 rules, applied without editing them.

Reads the coalesced holdings from the parse stage, adds Dhruvi's roll-forward
evidence, keeps current-period holdings, and applies the rules named in
params.yaml (cleaning.rules) through clean.apply_rules. Rules live in
src/lookthrough/clean.py and are never edited here.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import clean, paths, pipeline

P = paths.load_params(ROOT)
work = ROOT / "outputs" / "work"

h = pd.read_parquet(work / "holdings.parquet")
h = clean.add_rollforward_evidence(h)
rules = pipeline.configured_rules(P)
kept, log = clean.apply_rules(h[h["is_current"]], rules)
kept = clean.flag_debt(kept)

kept.to_parquet(work / "kept.parquet", index=False)
log.to_parquet(work / "log.parquet", index=False)

n_current = int(h["is_current"].sum())
print(f"clean: {len(rules)} rules, {n_current} current holdings, "
      f"{len(kept)} kept, {n_current - len(kept)} dropped")