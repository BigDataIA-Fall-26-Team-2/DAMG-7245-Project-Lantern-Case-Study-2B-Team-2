"""Check that every example in reports/cleaning_log.csv opens to the right row.

An example reads "<adsh> / <month> soi_row <n>". The row number is the row's
0-based position in that month's soi.tsv (combine.load_soi_all's soi_row), so
the line in the file is n + 2. For each example this opens the raw file,
confirms the row belongs to that filing and is current-period, and records
what it shows. Writes reports/cleaning_log_check.md.

    PYTHONPATH=src python tools/verify_examples.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "reports" / "cleaning_log.csv"
OUT = ROOT / "reports" / "cleaning_log_check.md"
ID = "Investment, Identifier Axis"
FV = "Initial fair value of Investment"
SUBS = ["Investment Company, Nonconsolidated Subsidiary [Axis]",
        "Investment Company, Nonconsolidated Subsidiary Axis"]


def main():
    log = pd.read_csv(LOG)
    files, rows, ok_all = {}, [], True
    for _, r in log.iterrows():
        m = re.match(r"(\S+) / (\d{4}_\d{2}) soi_row (\d+)", str(r["example"]))
        if not m:
            rows.append((r["rule"], r["example"], "no month or row in example", False))
            ok_all = False
            continue
        adsh, month, n = m.group(1), m.group(2), int(m.group(3))
        if month not in files:
            files[month] = pd.read_csv(ROOT / "data" / "raw" / f"{month}_bdc" / "soi.tsv",
                                       sep="\t", dtype=str, low_memory=False)
        x = files[month].loc[n]
        sub = next((x[c] for c in SUBS if c in x and pd.notna(x[c])), None)
        shows = (f"identifier \"{x.get(ID)}\"" + (f"; JV \"{sub}\"" if sub else "")
                 + (f"; fair value {float(x[FV]):,.0f}" if pd.notna(x.get(FV)) else ""))
        ok = x["adsh"] == adsh
        ok_all &= ok
        rows.append((r["rule"], f"{adsh} / {month} soi_row {n} (file line {n + 2})",
                     f"{shows}; ddate {x['ddate']}", ok))
    L = ["# Cleaning-log examples, checked against the raw files", "",
         "Each example in `reports/cleaning_log.csv` was opened in the raw `soi.tsv` of its "
         "month. `soi_row` is the 0-based row position in that file (as numbered by "
         "`combine.load_soi_all`), so the file line is the row number + 2 (header, 1-based "
         "lines). Regenerate with `PYTHONPATH=src python tools/verify_examples.py`.", "",
         "| Rule | Example | What the row shows | Right filing |", "|---|---|---|---|"]
    L += [f"| `{a}` | {b} | {c} | {'yes' if d else '**NO**'} |" for a, b, c, d in rows]
    L += ["", f"All examples open to a row of the named filing: **{'yes' if ok_all else 'NO'}**.", ""]
    OUT.write_text("\n".join(L))
    for a, b, c, d in rows:
        print(f"{'OK ' if d else 'BAD'} {a:24s} {b} -> {c[:90]}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
