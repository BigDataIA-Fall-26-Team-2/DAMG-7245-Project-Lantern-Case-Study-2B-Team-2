import argparse
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import paths, load

def select_sample(panel, seed=7):
    """Stable draw: total/FV rankings use identity ties; random picks use SHA-256.

    Independent of input row order and pandas/NumPy random generator versions.
    """
    import hashlib
    keys = ["adsh", "release", "identifier", "source_rows"]
    panel = panel.copy()
    panel[keys] = panel[keys].fillna("").astype(str)
    if panel.duplicated(keys).any():
        raise ValueError("Sampling requires unique holding provenance keys")
    panel = panel.sort_values(keys).reset_index(drop=True)
    size = (panel.groupby("adsh")["fair_value"].sum().rename("total").reset_index()
            .sort_values(["total", "adsh"], ascending=[False, True]))

    def rank(parts):
        import json
        return hashlib.sha256(json.dumps([seed, *parts], ensure_ascii=True).encode()).hexdigest()

    largest = size.adsh.iloc[:5].tolist()
    others = sorted(size.adsh.iloc[5:], key=lambda a: (rank([a]), a))[:5]
    picks = []
    for adsh in largest + others:
        group = panel[panel.adsh.eq(adsh)].sort_values(
            ["fair_value", *keys], ascending=[False, True, True, True, True], na_position="last")
        picks.append(group.head(1))
        if len(group) > 1:
            rest = group.iloc[1:]
            chosen = min(rest.index, key=lambda i: (rank(rest.loc[i, keys].tolist()), i))
            picks.append(rest.loc[[chosen]])
    return pd.concat(picks) if picks else panel.iloc[:0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/spot_check_sample_new.csv")
    ap.add_argument("--replace", action="store_true")
    args = ap.parse_args()
    out = ROOT / args.out

    REVIEW = ["filing_fair_value", "filing_principal", "matches", "note"]
    if out.exists() and not args.replace:
        old = pd.read_csv(out, dtype=str, keep_default_na=False)
        done = int(old[[c for c in REVIEW if c in old]].ne("").any(axis=1).sum())
        if done:
            sys.exit(f"{out.name}: {done} completed reviews, not overwritten (use --replace)")

    P = paths.load_params(ROOT)
    panel = pd.read_parquet(ROOT / P["outputs"]["panel"] / "holdings.parquet")

    sample = select_sample(panel)

    urls = {}
    for rel in P["releases"]:
        sub = load.load_sub(ROOT / P["data"]["raw_dir"] / f"{rel}_bdc")
        for a, u in zip(sub["adsh"], sub["inlineurl"]):
            urls.setdefault(a, u)

    sample = sample.assign(filing_url=sample["adsh"].map(urls),
                           **{c: "" for c in REVIEW})
    cols = ["adsh", "release", "name", "identifier", "is_debt", "fair_value", "principal",
            "source_rows", "filing_url"] + REVIEW
    sample[cols].to_csv(out, index=False)

    print(out.name, len(sample), "holdings", sample["adsh"].nunique(), "filings",
          int(sample["filing_url"].isna().sum()), "missing_url")


if __name__ == "__main__":
    main()
