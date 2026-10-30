"""Deterministic provenance-based samples shared by the CLI and app."""
import pandas as pd

def select_sample(panel, seed=7, n_largest=5, n_random=5, per_filing=2):
    """Stable draw: total/FV rankings use identity ties; random picks use SHA-256.

    Independent of input row order and pandas/NumPy random generator versions.
    """
    if min(n_largest, n_random, per_filing) < 0:
        raise ValueError("Sample counts must be nonnegative")
    if panel.empty or per_filing == 0 or n_largest + n_random == 0:
        return panel.iloc[:0].copy()
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

    largest = size.adsh.iloc[:n_largest].tolist()
    others = sorted(size.adsh.iloc[n_largest:], key=lambda a: (rank([a]), a))[:n_random]
    picks = []
    for adsh in largest + others:
        group = panel[panel.adsh.eq(adsh)].sort_values(
            ["fair_value", *keys], ascending=[False, True, True, True, True], na_position="last")
        picks.append(group.head(1))
        if len(group) > 1 and per_filing > 1:
            rest = group.iloc[1:]
            chosen = sorted(rest.index, key=lambda i: (rank(rest.loc[i, keys].tolist()), i))[:per_filing - 1]
            picks.append(rest.loc[chosen])
    return pd.concat(picks) if picks else panel.iloc[:0]

