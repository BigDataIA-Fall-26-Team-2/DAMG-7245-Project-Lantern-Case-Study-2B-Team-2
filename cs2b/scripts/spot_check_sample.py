import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import paths, load

P = paths.load_params(ROOT)
panel = pd.read_parquet(ROOT / P["outputs"]["panel"] / "holdings.parquet")

size = panel.groupby("adsh")["fair_value"].sum().sort_values(ascending=False)
others = size.index[5:].to_series()
chosen = list(size.index[:5]) + list(others.sample(min(5, len(others)), random_state=7))

picks = []
for a in chosen:
    g = panel[panel["adsh"] == a].sort_values("fair_value", ascending=False)
    picks.append(g.head(1))
    if len(g) > 1:
        picks.append(g.iloc[1:].sample(1, random_state=7))
sample = pd.concat(picks)

urls = {}
for rel in P["releases"]:
    sub = load.load_sub(ROOT / P["data"]["raw_dir"] / f"{rel}_bdc")
    for a, u in zip(sub["adsh"], sub["inlineurl"]):
        urls.setdefault(a, u)

sample = sample.assign(filing_url=sample["adsh"].map(urls),
                       filing_fair_value="", filing_principal="", matches="", note="")
cols = ["adsh", "release", "name", "identifier", "is_debt", "fair_value", "principal",
        "source_rows", "filing_url", "filing_fair_value", "filing_principal", "matches", "note"]
out = ROOT / P["outputs"]["reports"] / "spot_check.csv"
sample[cols].to_csv(out, index=False)

print(len(sample), "holdings", sample["adsh"].nunique(), "filings",
      int(sample["filing_url"].isna().sum()), "missing_url")