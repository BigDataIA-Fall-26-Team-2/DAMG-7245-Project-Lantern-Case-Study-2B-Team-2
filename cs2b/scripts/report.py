"""Stage 5 (report): write the panel and every report.

Calls report.write_outputs, which writes outputs/panel/holdings.parquet
(admitted filings only) and reports/coverage.csv, coverage.json, coverage.md,
triage.md and cleaning_log.csv. Reads data/triage.csv but never edits it.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import paths, report

P = paths.load_params(ROOT)
work = ROOT / "outputs" / "work"

kept = pd.read_parquet(work / "kept.parquet")
rec = pd.read_parquet(work / "rec.parquet")
diag = pd.read_parquet(work / "diag.parquet")
log = pd.read_parquet(work / "log.parquet")
sub = pd.read_parquet(work / "sub.parquet")

result = report.write_outputs(kept, rec, diag, log, ROOT, P, sub=sub)
print("report: wrote panel and reports")
print(result)