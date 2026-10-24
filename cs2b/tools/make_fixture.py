"""Build the synthetic fixture release (data/fixture/2026_08_bdc/) in the SEC BDC data-set layout.

Every BDC, borrower and number here is FICTIONAL. The fixture exists so the notebooks and tests run
offline; it copies the real file layout (SEC BDC readme) and five artifacts real releases contain.
"""
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "fixture" / "2026_08_bdc"
V = "us-gaap/2025"
PERIOD, PRIOR, FILED = "2026-06-30", "2025-12-31", "2026-08-12"
SOI_COLS = ["adsh", "cik", "name", "ddate", "form", "filed", "period", "inlineurl", "cstm", "qtrs",
            "Industry Sector Axis", "Investment, Identifier Axis", "Investment, Issuer Affiliation Axis",
            "Investment Type Axis", "Investment Interest Rate", "Investment, Basis Spread, Variable Rate",
            "Investment Maturity Date", "Investment Owned, Balance, Principal Amount", "Investment Owned, Cost",
            "Investment Owned, Fair Value", "Investment Owned, Net Assets, Percentage",
            "Investment, Interest Rate, Paid in Kind"]
SUB_COLS = ["adsh", "cik", "name", "countryba", "stprba", "cityba", "zipba", "bas1", "bas2", "baph",
            "countryma", "stprma", "cityma", "zipma", "mas1", "mas2", "countryinc", "stprinc", "ein",
            "former", "changed", "afs", "wksi", "fye", "form", "period", "fy", "fp", "filed", "accepted",
            "prevrpt", "detail", "instance", "pubfloatusd", "floatdate", "inlineurl"]
TAG_COLS = ["tag", "version", "custom", "abstract", "datatype", "iord", "crdr", "tlabel", "doc"]
NUM_COLS = ["adsh", "tag", "version", "ddate", "qtrs", "uom", "segments", "dimn", "value", "footnote", "footlen"]
LABELS = {"InvestmentOwnedAtFairValue": "Investment Owned, Fair Value", "InvestmentOwnedAtCost": "Investment Owned, Cost",
          "InvestmentOwnedBalancePrincipalAmount": "Investment Owned, Balance, Principal Amount",
          "InvestmentInterestRate": "Investment Interest Rate",
          "InvestmentBasisSpreadVariableRate": "Investment, Basis Spread, Variable Rate",
          "InvestmentMaturityDate": "Investment Maturity Date",
          "InvestmentOwnedPercentOfNetAssets": "Investment Owned, Net Assets, Percentage",
          "InvestmentInterestRatePaidInKind": "Investment, Interest Rate, Paid in Kind"}
BDCS = {  # key: (adsh, cik, name, net assets)
    "A": ("0009000001-26-000101", "9000000001", "FIXTURE ALPHA CAPITAL CORP", 150_000_000),
    "B": ("0009000002-26-000202", "9000000002", "FIXTURE BRAVO LENDING FUND", 140_000_000),
    "B0": ("0009000002-26-000201", "9000000002", "FIXTURE BRAVO LENDING FUND", 140_000_000),
    "C": ("0009000003-26-000301", "9000000003", "FIXTURE CHARLIE CREDIT BDC", 120_000_000),
    "D": ("0009000004-26-000401", "9000000004", "FIXTURE DELTA PRIVATE CREDIT FUND", 110_000_000),
    "E": ("0009000005-26-000501", "9000000005", "FIXTURE ECHO VENTURE LENDING", 60_000_000),
    "F": ("0009000006-26-000601", "9000000006", "FIXTURE FOXTROT SENIOR LOAN FUND", 70_000_000),
}
BORROWERS = ["Northwind Logistics LLC", "Harbor Point Software Inc.", "Cedar Ridge Dental Partners LLC",
             "Bluefin Packaging Holdings Corp.", "Summit Lane HVAC Services LLC", "Ironwood Data Systems Inc.",
             "Meadowbrook Pet Care LLC", "Granite Peak Insurance Brokers LLC", "Lumen Bay Analytics Inc.",
             "Silver Creek Foods LLC", "Copperline Telecom Holdings LLC", "Riverton Learning Inc."]
INDUSTRY = ["Transportation Sector [Member]", "Software Sector [Member]", "Healthcare Sector [Member]",
            "Industrial Sector [Member]", "Industrial Sector [Member]", "Software Sector [Member]",
            "Consumer Sector [Member]", "Financial Services Sector [Member]", "Software Sector [Member]",
            "Consumer Sector [Member]", "Telecommunications Sector [Member]", "Education Sector [Member]"]
UNAFF = "Investment, Unaffiliated Issuer [Member]"
FMT = lambda d: f"{d[5:7]}/{d[8:10]}/{d[:4]}"   # SOI dates are MM/DD/YYYY


def holding(i, kind="First Lien Senior Secured Loan", spread=0.0525, base=0.043, principal=20_000_000,
            price=0.99, mat="2030-06-30", pik=None, equity=False, prior_base=0.0455):
    b = BORROWERS[i % len(BORROWERS)]
    if equity:
        ident = f"{kind} | {b}"
        return dict(borrower=b, ident=ident, ident_prior=ident, type=kind, industry=INDUSTRY[i % 12],
                    principal=None, cost=float(principal), fv=round(principal * price), rate=None, spread=None,
                    mat=None, pik=None)
    rate = round(base + spread, 4)
    tail = f"S + {spread*100:.2f}% ({rate*100:.2f}%) | {mat[5:7]}/{mat[:4]}"
    tail_prior = f"S + {spread*100:.2f}% ({(prior_base+spread)*100:.2f}%) | {mat[5:7]}/{mat[:4]}"
    return dict(borrower=b, ident=f"{kind} | {b} | {tail}", ident_prior=f"{kind} | {b} | {tail_prior}",
                type=kind, industry=INDUSTRY[i % 12], principal=float(principal),
                cost=round(principal * 0.985), fv=round(principal * price), rate=rate, spread=spread, mat=mat, pik=pik)


def soi_row(key, ddate, h=None, **over):
    adsh, cik, name, na = BDCS[key]
    r = {c: "" for c in SOI_COLS}
    r.update({"adsh": adsh, "cik": cik, "name": name, "ddate": FMT(ddate), "form": "10-Q",
              "filed": FMT("2026-08-05" if key == "B0" else FILED), "period": FMT(PERIOD),
              "inlineurl": f"https://www.sec.gov/ix?doc=/Archives/edgar/data/{int(cik)}/{adsh.replace('-', '')}/fixture.htm",
              "cstm": "1" if key in ("E", "F") else "2", "qtrs": "0"})
    if h is not None:
        r["Investment, Identifier Axis"] = h["ident"] if ddate == PERIOD else h["ident_prior"]
    r.update({k: ("" if v is None else str(v)) for k, v in over.items()})
    return r


def values(h, na, fields):
    m = {"Investment Owned, Fair Value": h["fv"], "Investment Owned, Cost": h["cost"],
         "Investment Owned, Balance, Principal Amount": h["principal"], "Investment Interest Rate": h["rate"],
         "Investment, Basis Spread, Variable Rate": h["spread"], "Investment Maturity Date": h["mat"],
         "Investment Owned, Net Assets, Percentage": round(h["fv"] / na, 4) if h["fv"] else None,
         "Investment, Interest Rate, Paid in Kind": h["pik"], "Industry Sector Axis": h["industry"],
         "Investment Type Axis": h["type"].split(" | ")[0] + " [Member]"}
    return {f: m[f] for f in fields}


ALL_VALUE_FIELDS = ["Industry Sector Axis", "Investment Type Axis", "Investment Interest Rate",
                    "Investment, Basis Spread, Variable Rate", "Investment Maturity Date",
                    "Investment Owned, Balance, Principal Amount", "Investment Owned, Cost",
                    "Investment Owned, Fair Value", "Investment Owned, Net Assets, Percentage",
                    "Investment, Interest Rate, Paid in Kind"]


def build():
    soi, num, sub = [], [], []
    hold = {}
    # ---- A: split rows + comparatives (clean)
    hold["A"] = [holding(i, principal=18_000_000 + 1_000_000 * i, price=0.97 + 0.004 * i) for i in range(8)]
    hold["A"][5]["pik"] = 0.02
    for ddate, hs in ((PERIOD, hold["A"]), (PRIOR, hold["A"][:6])):
        for h in hs:
            na = BDCS["A"][3]
            soi.append(soi_row("A", ddate, h, **values(h, na, ["Industry Sector Axis", "Investment Type Axis",
                                                               "Investment Owned, Fair Value", "Investment Owned, Cost"])))
            soi.append(soi_row("A", ddate, h, **values(h, na, ["Investment Owned, Balance, Principal Amount",
                                                               "Investment Interest Rate", "Investment, Basis Spread, Variable Rate",
                                                               "Investment Maturity Date"])))
            soi.append(soi_row("A", ddate, h, **values(h, na, ["Investment Owned, Net Assets, Percentage",
                                                               "Investment, Interest Rate, Paid in Kind"])))
    # ---- B and B0: subtotals, a total row, a money-market line; B0 is the superseded original
    hold["B"] = [holding(i + 2, kind=("Second Lien Senior Secured Loan" if i >= 6 else "First Lien Senior Secured Loan"),
                         principal=15_000_000 + 1_500_000 * i, price=0.98) for i in range(8)]
    for key in ("B0", "B"):
        na = BDCS[key][3]
        for j, h in enumerate(hold["B"]):
            v = values(h, na, ALL_VALUE_FIELDS)
            if key == "B0" and j == 3:
                v["Investment Owned, Fair Value"] = h["fv"] * 10        # the error the amendment fixed
            soi.append(soi_row(key, PERIOD, h, **v))
        first = sum(h["fv"] for h in hold["B"] if h["type"].startswith("First"))
        second = sum(h["fv"] for h in hold["B"] if h["type"].startswith("Second"))
        soi.append(soi_row(key, PERIOD, **{"Investment Type Axis": "First Lien Senior Secured Debt [Member]",
                                            "Investment Owned, Fair Value": first}))
        soi.append(soi_row(key, PERIOD, **{"Investment Type Axis": "Second Lien Senior Secured Debt [Member]",
                                            "Investment Owned, Fair Value": second}))
        soi.append(soi_row(key, PERIOD, **{"Investment, Identifier Axis": "Total Investments",
                                            "Investment Owned, Fair Value": first + second}))
        soi.append(soi_row(key, PERIOD, **{"Investment, Identifier Axis": "Money Market Fund | Fixture Government Portfolio | Institutional Class",
                                            "Investment Owned, Fair Value": 5_000_000, "Investment Owned, Cost": 5_000_000}))
    # ---- C: every holding twice (restated copy), one copy disagrees; affiliate categories
    hold["C"] = [holding(i + 4, principal=14_000_000 + 1_200_000 * i, price=0.985) for i in range(8)]
    aff = [UNAFF] * 5 + ["Investment, Affiliated Issuer, Noncontrolled [Member]"] * 2 + ["Investment, Affiliated Issuer, Controlled [Member]"]
    na = BDCS["C"][3]
    for j, h in enumerate(hold["C"]):
        v = values(h, na, ALL_VALUE_FIELDS)
        soi.append(soi_row("C", PERIOD, h, **v, **{"Investment, Issuer Affiliation Axis": aff[j]}))
        v2 = dict(v)
        if j == 2:
            v2["Investment Owned, Fair Value"] = h["fv"] + 10_000           # the conflicting copy
        soi.append(soi_row("C", PERIOD, h, **v2))
    # ---- D: revolver and delayed draw; unfunded commitments netted out of the filed total
    hold["D"] = [holding(i + 6, principal=19_000_000 + 1_000_000 * i, price=0.99) for i in range(6)] + \
                [holding(10, kind="First Lien Revolver", principal=10_000_000, price=0.99),
                 holding(11, kind="First Lien Delayed Draw Term Loan", principal=12_000_000, price=0.99)]
    for h in hold["D"]:
        soi.append(soi_row("D", PERIOD, h, **values(h, BDCS["D"][3], ALL_VALUE_FIELDS)))
    # ---- E: venture lender; custom tag hides three fair values from SOI; equity and warrants
    hold["E"] = [holding(i + 1, kind="Growth Capital Term Loan", spread=0.0700, principal=6_000_000 + 500_000 * i,
                         price=0.97, pik=0.015 if i % 2 else None) for i in range(6)] + \
                [holding(1, kind="Warrants to Purchase Series C Preferred Stock", principal=400_000, price=1.6, equity=True),
                 holding(3, kind="Series B Preferred Stock", principal=2_000_000, price=1.25, equity=True),
                 holding(8, kind="Common Stock", principal=900_000, price=0.7, equity=True)]
    hidden = {0, 2, 4}
    for j, h in enumerate(hold["E"]):
        v = values(h, BDCS["E"][3], ALL_VALUE_FIELDS)
        if j in hidden:
            v["Investment Owned, Fair Value"] = None; v["Investment Owned, Net Assets, Percentage"] = None
        soi.append(soi_row("E", PERIOD, h, **v))

    # ---- F: holdings on a CUSTOM identifier axis, which SOI drops: only type subtotals survive
    hold["F"] = [holding(i + 3, principal=9_000_000 + 1_000_000 * i, price=0.995) for i in range(8)]
    f_total = sum(h["fv"] for h in hold["F"])
    soi.append(soi_row("F", PERIOD, **{"Investment Type Axis": "First Lien Senior Secured Debt [Member]",
                                        "Investment Owned, Fair Value": f_total}))
    soi.append(soi_row("F", PERIOD, **{"Industry Sector Axis": "Software Sector [Member]",
                                        "Investment Owned, Fair Value": sum(h["fv"] for h in hold["F"] if h["industry"].startswith("Software"))}))
    soi.append(soi_row("F", PERIOD, **{"Investment, Issuer Affiliation Axis": UNAFF, "Investment Owned, Fair Value": f_total}))

    # ---- NUM: filed totals, per-holding facts, category facts, netting, custom-tag facts
    def nrow(key, tag, ddate, value, segments="", dimn="0", version=V, uom="USD"):
        num.append({"adsh": BDCS[key][0], "tag": tag, "version": version, "ddate": ddate.replace("-", ""),
                    "qtrs": "0", "uom": uom, "segments": segments, "dimn": dimn, "value": f"{value:.4f}",
                    "footnote": "", "footlen": "0"})
    ident_seg = lambda txt: f"InvestmentIdentifierAxis({V})={txt}()"
    for key in ("A", "B", "C", "D", "E", "F"):
        hs = hold[key]
        total = sum(h["fv"] for h in hs)
        if key == "D":
            total -= 3_000_000
            nrow("D", "InvestmentOwnedAtFairValue", PERIOD, -3_000_000,
                 f"InvestmentTypeAxis({V})=UnfundedLoanCommitmentsMember({BDCS['D'][0]})", "1")
        nrow(key, "InvestmentOwnedAtFairValue", PERIOD, total)
        for j, h in enumerate(hs):
            if key == "E" and j in hidden:
                nrow("E", "InvestmentFairValueCustom", PERIOD, h["fv"], ident_seg(h["ident"]), "1", version=BDCS["E"][0])
            elif key == "F":
                nrow("F", "InvestmentOwnedAtFairValue", PERIOD, h["fv"],
                     f"InvestmentPositionCustomAxis({BDCS['F'][0]})={h['ident']}()", "1")
            else:
                nrow(key, "InvestmentOwnedAtFairValue", PERIOD, h["fv"], ident_seg(h["ident"]), "1")
        if key == "C":
            for member, tagm in ((UNAFF, "InvestmentUnaffiliatedIssuerMember"),
                                 ("Investment, Affiliated Issuer, Noncontrolled [Member]", "InvestmentAffiliatedIssuerNoncontrolledMember"),
                                 ("Investment, Affiliated Issuer, Controlled [Member]", "InvestmentAffiliatedIssuerControlledMember")):
                val = sum(h["fv"] for h, a in zip(hs, aff) if a == member)
                nrow("C", "InvestmentOwnedAtFairValue", PERIOD, val, f"InvestmentIssuerAffiliationAxis({V})={tagm}({V})", "1")
    nrow("A", "InvestmentOwnedAtFairValue", PRIOR, sum(h["fv"] for h in hold["A"][:6]))
    b0 = sum(h["fv"] for h in hold["B"]) + 9 * hold["B"][3]["fv"]
    num.append({"adsh": BDCS["B0"][0], "tag": "InvestmentOwnedAtFairValue", "version": V, "ddate": PERIOD.replace("-", ""),
                "qtrs": "0", "uom": "USD", "segments": "", "dimn": "0", "value": f"{b0:.4f}", "footnote": "", "footlen": "0"})
    for key in ("A", "B", "C", "D", "E", "F"):
        nrow(key, "NetAssets", PERIOD, BDCS[key][3])

    # ---- SUB and TAG
    for key in ("A", "B0", "B", "C", "D", "E", "F"):
        adsh, cik, name, _ = BDCS[key]
        r = {c: "" for c in SUB_COLS}
        r.update({"adsh": adsh, "cik": cik, "name": name, "countryba": "US", "countryinc": "US", "stprinc": "MD",
                  "wksi": "0", "fye": "1231", "form": "10-Q/A" if key == "B" else "10-Q", "period": PERIOD.replace("-", ""),
                  "fy": "2026", "fp": "Q2", "filed": ("2026-08-05" if key == "B0" else FILED).replace("-", ""),
                  "accepted": ("2026-08-05" if key == "B0" else FILED) + " 16:05:00", "prevrpt": "1" if key == "B0" else "0",
                  "detail": "1", "instance": f"fixture{key.lower()}-20260630_htm.xml",
                  "inlineurl": f"https://www.sec.gov/ix?doc=/Archives/edgar/data/{int(cik)}/{adsh.replace('-', '')}/fixture.htm"})
        sub.append(r)
    tag = [{"tag": t, "version": V, "custom": "0", "abstract": "0", "datatype": "monetary", "iord": "I", "crdr": "D",
            "tlabel": l, "doc": ""} for t, l in LABELS.items()]
    tag.append({"tag": "NetAssets", "version": V, "custom": "0", "abstract": "0", "datatype": "monetary", "iord": "I",
                "crdr": "C", "tlabel": "Net Assets", "doc": ""})
    tag.append({"tag": "InvestmentFairValueCustom", "version": BDCS["E"][0], "custom": "1", "abstract": "0",
                "datatype": "monetary", "iord": "I", "crdr": "D", "tlabel": "Fair value of investment (custom)", "doc": ""})
    return soi, num, sub, tag


def write(path, cols, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t", lineterminator="\n")
        w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    soi, num, sub, tag = build()
    write(OUT / "soi.tsv", SOI_COLS, soi)
    write(OUT / "datasets" / "num.tsv", NUM_COLS, num)
    write(OUT / "datasets" / "sub.tsv", SUB_COLS, sub)
    write(OUT / "datasets" / "tag.tsv", TAG_COLS, tag)
    (OUT / "FIXTURE_README.txt").write_text("SYNTHETIC FIXTURE. All BDCs, borrowers and numbers are fictional.\n"
                                            "Layout follows the SEC BDC data-set readme. Built by tools/make_fixture.py.\n")
    print(f"fixture written to {OUT}: soi {len(soi)} rows, num {len(num)}, sub {len(sub)}, tag {len(tag)}")
