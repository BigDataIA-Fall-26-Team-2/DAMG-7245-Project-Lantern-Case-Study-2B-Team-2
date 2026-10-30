"""Run the LANTERN pipeline in memory with settings chosen by the user.

Follows the dvc.yaml stages: source (manifest) -> read (parse) -> clean -> compare
(reconcile). Reading is slow, so it runs once per set of releases and is kept in
memory. For the team's own releases it starts from outputs/work/*.parquet (restored
by dvc pull) instead of the raw files. Nothing here writes to outputs/ or reports/.
"""
import datetime as dt
import json
import re
import shutil
import sys
import threading
import uuid
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import acquire, clean, combine, holdings, paths, reconcile, report  # noqa: E402,F401

P = paths.load_params(ROOT)
RULE_NAMES = [r.__name__ for r in clean.RULES]
DEFAULT_RULES = P.get("cleaning", {}).get("rules", RULE_NAMES)
DEFAULT_TOLERANCE = float(P["reconcile"]["tolerance"])
DEFAULT_RELEASES = sorted(P.get("releases", [P["release"]]))
WORK = ROOT / "outputs" / "work"
RAW = ROOT / P["data"]["raw_dir"]
UPLOADS = ROOT / "data" / "uploads"
UPLOAD_MANIFEST = UPLOADS / "manifest.json"
RELEASE_RE = re.compile(r"\d{4}(?:_(?:0[1-9]|1[0-2])|q[1-4])")
NEEDED = ("soi.tsv", "datasets/sub.tsv", "datasets/num.tsv", "datasets/tag.tsv")
MAX_RUNS = 10

FILING_COLS = ["adsh", "cik", "name", "form", "period", "release", "n_holdings", "missing_fv",
               "holdings_fv", "filed_fv", "filed_total_status", "gap_pct", "admitted",
               "triage_category", "triage_saved_category", "triage_stale", "triage_complete", "triage_evidence", "triage_example", "triage_fix", "triage_status",
               "filing_url"]
HOLDING_COLS = [c for c in report.PANEL_COLS + report.SOURCE_COLUMNS if c not in ("cik", "name", "period")]
SAMPLE_COLS = ["adsh", "release", "name", "identifier", "is_debt", "fair_value", "principal",
               "source_rows", "filing_url"]

_inputs, _runs = {}, {}
_lock = threading.Lock()


def records(df: pd.DataFrame) -> list:
    """JSON-safe rows: numpy types become plain Python, NaN becomes null."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _folders(base: Path) -> dict:
    if not base.exists():
        return {}
    return {d.name[: -len("_bdc")]: d for d in base.glob("*_bdc")
            if d.is_dir() and (d / "datasets" / "sub.tsv").is_file()}


def release_dirs() -> dict:
    """Team releases (data/raw, DVC) and added ones (data/uploads). Team copies win."""
    return {**_folders(UPLOADS), **_folders(RAW)}


def available_releases() -> list:
    return sorted(release_dirs())


def _upload_manifest() -> list:
    return json.loads(UPLOAD_MANIFEST.read_text()) if UPLOAD_MANIFEST.exists() else []


def releases_info() -> list:
    team = set(_folders(RAW))
    added = {e["release"]: e for e in _upload_manifest()}
    out = []
    for r in available_releases():
        e = added.get(r, {})
        out.append({"release": r, "origin": "team data (DVC)" if r in team else e.get("origin", "added"),
                    "removable": r not in team, "sha256": e.get("sha256"), "bytes": e.get("bytes")})
    return out


def _register(zip_path: Path, release: str, origin: str) -> dict:
    """Unpack an added ZIP, check it is an SEC BDC data set, fingerprint it."""
    try:
        folder = acquire.unzip_release(zip_path, UPLOADS, release)
    except Exception as e:
        zip_path.unlink(missing_ok=True)
        shutil.rmtree(UPLOADS / f".unzip_{release}", ignore_errors=True)
        raise ValueError(f"not an SEC BDC data set ZIP: {e}")
    missing = [n for n in NEEDED if not (folder / n).is_file()]
    if missing:
        shutil.rmtree(folder, ignore_errors=True)
        zip_path.unlink(missing_ok=True)
        raise ValueError(f"ZIP is missing {missing}")
    entry = {"release": release, "origin": origin,
             "path": zip_path.relative_to(ROOT).as_posix(), "bytes": zip_path.stat().st_size,
             "sha256": acquire.sha256_file(zip_path), "recorded": dt.date.today().isoformat()}
    entries = [e for e in _upload_manifest() if e["release"] != release] + [entry]
    UPLOAD_MANIFEST.write_text(json.dumps(entries, indent=2))
    return entry


def _check_new(release: str) -> str:
    release = (release or "").strip()
    if not RELEASE_RE.fullmatch(release):
        raise ValueError("release name must look like 2026_08 (month) or 2025q4 (quarter)")
    if release in available_releases():
        raise ValueError(f"{release} is already available")
    UPLOADS.mkdir(parents=True, exist_ok=True)
    return release


def add_upload(release: str, data: bytes) -> dict:
    release = _check_new(release)
    z = UPLOADS / f"{release}_bdc.zip"
    z.write_bytes(data)
    return _register(z, release, "uploaded")


def add_from_sec(release: str) -> dict:
    release = _check_new(release)
    try:
        z = acquire.download_release(release, UPLOADS, P["sec"]["user_agent"], P["sec"]["base_url"])
    except Exception as e:
        raise ValueError(f"could not download {release} from the SEC: {e}")
    return _register(z, release, "downloaded from SEC")


def remove_release(release: str) -> dict:
    if release in _folders(RAW):
        raise ValueError(f"{release} is team data (DVC) and cannot be removed here")
    if release not in _folders(UPLOADS):
        raise KeyError(release)
    shutil.rmtree(UPLOADS / f"{release}_bdc", ignore_errors=True)
    (UPLOADS / f"{release}_bdc.zip").unlink(missing_ok=True)
    UPLOAD_MANIFEST.write_text(json.dumps(
        [e for e in _upload_manifest() if e["release"] != release], indent=2))
    with _lock:
        for k in [k for k in _inputs if release in k]:
            _inputs.pop(k)
    return {"removed": release}


def rule_docs() -> dict:
    return {r.__name__: " ".join((r.__doc__ or "").split()) for r in clean.RULES}


def config() -> dict:
    return {"releases": available_releases(), "default_releases": DEFAULT_RELEASES,
            "rules": RULE_NAMES, "default_rules": DEFAULT_RULES, "rule_docs": rule_docs(),
            "default_tolerance": DEFAULT_TOLERANCE,
            "loaded_release_sets": [list(k) for k in _inputs]}


def source() -> dict:
    """Step 1: the SEC files we use, their fingerprints, and whether they still match."""
    mpath = ROOT / "data" / "manifest.json"
    if not mpath.exists():
        return {"files": [], "mismatches": [], "manifest_found": False}
    files = json.loads(mpath.read_text())
    bad = acquire.verify_manifest(mpath, root=ROOT)
    return {"files": files, "mismatches": bad, "manifest_found": True}


def _work_ready() -> bool:
    return all((WORK / f"{n}.parquet").exists() for n in ("sub", "num", "canon", "holdings"))


def _prepare(releases: tuple) -> dict:
    with _lock:
        if releases not in _inputs:
            if list(releases) == DEFAULT_RELEASES and _work_ready():
                sub = pd.read_parquet(WORK / "sub.parquet")
                num = pd.read_parquet(WORK / "num.parquet")
                canon = pd.read_parquet(WORK / "canon.parquet")
                h = pd.read_parquet(WORK / "holdings.parquet")
                origin = "outputs/work (parse stage output, restored by dvc pull)"
            else:
                every = release_dirs()
                dirs = {r: every[r] for r in releases}
                inp = combine.load_inputs(dirs, num_tags=[reconcile.FV_TAG], custom_fv=True,
                                          **paths.source_evidence_paths(P, ROOT))
                sub, num = inp["sub"], inp["num"]
                canon = holdings.split_periods(inp["canon"], sub)
                h = holdings.coalesce_holdings(canon)
                origin = "raw SEC files in data/raw"
            h = clean.add_rollforward_evidence(h)
            per_month = (sub.groupby("release").size().rename("reports").to_frame()
                         .join(canon.groupby("release").size().rename("soi_rows"), how="outer")
                         .reindex(list(releases)).fillna(0).astype(int)
                         .rename_axis("release").reset_index())
            _inputs[releases] = {
                "sub": sub,
                "current": h[h["is_current"]],
                "filed": reconcile.filed_totals(num, sub),
                "soi_adsh": set(canon["adsh"]),
                "read": {"origin": origin, "reports": int(len(sub)),
                         "reports_with_soi": int(canon["adsh"].nunique()),
                         "soi_rows": int(len(canon)),
                         "current_rows": int(canon["is_current"].sum()),
                         "comparative_rows": int((~canon["is_current"]).sum()),
                         "holdings": int(len(h)),
                         "current_holdings": int(h["is_current"].sum()),
                         "per_month": records(per_month)},
            }
        return _inputs[releases]


def refresh() -> dict:
    """Forget everything in memory, so the next run reads the files on disk again."""
    with _lock:
        _inputs.clear()
        _runs.clear()
    return {"refreshed": True}


def warm_up() -> None:
    """Prepare the team's releases in the background when the backend starts."""
    try:
        _prepare(tuple(DEFAULT_RELEASES))
    except Exception:  # a failed warm-up is reported by the first real run
        pass


TRIAGE_ERROR = {"message": None}


def _triage() -> pd.DataFrame:
    """Lokesh's human triage (data/triage.csv), read fresh on every run."""
    try:
        t = report.load_triage(ROOT / P.get("triage", {}).get("input", "data/triage.csv"))
        TRIAGE_ERROR["message"] = None
        return t
    except (ValueError, KeyError) as e:
        TRIAGE_ERROR["message"] = f"data/triage.csv could not be read: {e}"
        return pd.DataFrame()


def run(releases=None, tolerance=None, rules=None) -> dict:
    releases = tuple(sorted(releases or DEFAULT_RELEASES))
    tolerance = DEFAULT_TOLERANCE if tolerance is None else float(tolerance)
    rules = DEFAULT_RULES if rules is None else list(rules)
    unknown = sorted(set(releases) - set(available_releases()))
    if unknown:
        raise ValueError(f"releases not found in data/raw: {unknown}")
    bad = [r for r in rules if r not in RULE_NAMES]
    if bad:
        raise ValueError(f"unknown cleaning rules: {bad}")
    ordered = [getattr(clean, n) for n in DEFAULT_RULES if n in rules]
    ordered += [getattr(clean, n) for n in RULE_NAMES if n in rules and n not in DEFAULT_RULES]

    inp = _prepare(releases)
    kept, log = clean.apply_rules(inp["current"], ordered)
    if hasattr(clean, "clear_equity_principal"):
        kept, tlog = clean.clear_equity_principal(kept)
        log = pd.concat([log, pd.DataFrame([tlog])], ignore_index=True)
    log = _example_lines(log, inp["current"])
    kept = clean.flag_debt(kept)
    rec = reconcile.reconcile(kept, inp["filed"], inp["sub"], tolerance,
                              soi_adsh=inp["soi_adsh"])
    cov = reconcile.coverage(rec, inp["sub"])
    cov.pop("filings_without_soi_adsh", None)

    sub = inp["sub"].set_index("adsh")
    rec["release"] = rec["adsh"].map(sub["release"])
    rec["filing_url"] = rec["adsh"].map(sub["inlineurl"])
    tri = _triage()

    def from_triage(col):
        if tri.empty or col not in tri:
            return pd.Series([None] * len(rec), index=rec.index, dtype="object")
        return rec["adsh"].map(tri[col].replace("", pd.NA)).astype("object")

    cat = from_triage("triage_category")
    cat[~rec["admitted"] & cat.isna()] = "to_triage"
    cat[rec["admitted"]] = None
    rec["triage_category"] = cat
    for out, col in [("triage_evidence", "evidence"), ("triage_example", "example"),
                     ("triage_fix", "fix_or_reason"), ("triage_status", "review_status")]:
        v = from_triage(col)
        v[rec["admitted"]] = None
        rec[out] = v
    rec["triage_saved_category"] = rec["triage_category"]
    rec["triage_complete"] = False
    rec["triage_stale"] = False
    for idx, row in rec.loc[~rec["admitted"]].iterrows():
        entry = tri.loc[row.adsh] if row.adsh in tri.index else None
        complete, stale = report.triage_review_state(entry, row.holdings_fv, row.filed_fv)
        rec.loc[idx, ["triage_complete", "triage_stale"]] = [complete, stale]
        rec.loc[idx, "triage_status"] = "stale" if stale else ("reviewed" if complete else "incomplete")
        if not complete:
            rec.loc[idx, "triage_category"] = "to_triage"
    kept["filing_url"] = kept["adsh"].map(sub["inlineurl"])
    pr = pd.to_numeric(kept["principal"], errors="coerce")
    # The parser does not establish principal currency or distinguish every share
    # quantity from principal. Never turn these raw amounts into a quoted price.
    kept["price"] = float("nan")
    kept["check_currency"] = pr.notna()
    kept["price_status"] = "unverified principal currency/units"
    admitted = set(rec.loc[rec["admitted"], "adsh"])
    kept["in_final"] = kept["adsh"].isin(admitted)

    stats = {"read": inp["read"],
             "clean": {"current_holdings": int(len(inp["current"])), "kept": int(len(kept)),
                       "removed": int(len(inp["current"]) - len(kept))},
             "final": {"loans": int(kept["adsh"].isin(admitted).sum()),
                       "reports": int(len(admitted))}}
    rid = uuid.uuid4().hex[:8]
    settings = {"releases": list(releases), "tolerance": tolerance,
                "rules": [r.__name__ for r in ordered]}
    with _lock:
        _runs[rid] = {"settings": settings, "coverage": cov, "stats": stats,
                      "rec": rec, "kept": kept, "log": log}
        while len(_runs) > MAX_RUNS:
            _runs.pop(next(iter(_runs)))
    return summary(rid)


def _get(rid: str) -> dict:
    if rid not in _runs:
        raise KeyError(rid)
    return _runs[rid]


EXAMPLE_RE = re.compile(r"^(\S+) / (?:(\S+) )?soi_row (\d+)$")


def _example_lines(log: pd.DataFrame, current: pd.DataFrame) -> pd.DataFrame:
    """Add the removed line itself (its name and value) to each rule's example."""
    if log.empty:
        return log
    log = log.copy()
    names, values = [], []
    for ex in log["example"].fillna(""):
        m = EXAMPLE_RE.match(str(ex).strip())
        name = value = None
        if m:
            adsh, month, row = m.groups()
            c = current[current["adsh"].eq(adsh)]
            if month and "release" in c:
                c = c[c["release"].eq(month)]
            c = c[c["source_rows"].astype(str).str.split(";").map(lambda rows: row in rows)]
            if len(c):
                name, value = c["identifier"].iloc[0], c["fair_value"].iloc[0]
        names.append(name)
        values.append(None if value is None or pd.isna(value) else float(value))
    log["example_line"], log["example_value"] = names, values
    return log


def summary(rid: str) -> dict:
    r = _get(rid)
    return {"run_id": rid, "settings": r["settings"], "coverage": r["coverage"],
            "stats": r["stats"], "triage_error": TRIAGE_ERROR["message"],
            "cleaning_log": records(r["log"]) if len(r["log"]) else []}


def filings(rid: str, admitted=None, q=None) -> list:
    rec = _get(rid)["rec"]
    if admitted is not None:
        rec = rec[rec["admitted"].eq(admitted)]
    if q:
        rec = rec[rec["name"].str.contains(q, case=False, na=False, regex=False)]
    return records(rec[[c for c in FILING_COLS if c in rec]])


def filing_holdings(rid: str, adsh: str) -> dict:
    r = _get(rid)
    f = r["rec"][r["rec"]["adsh"].eq(adsh)]
    if f.empty:
        raise KeyError(adsh)
    h = r["kept"][r["kept"]["adsh"].eq(adsh)].sort_values("fair_value", ascending=False)
    return {"filing": records(f[[c for c in FILING_COLS if c in f]])[0],
            "holdings": records(h[[c for c in HOLDING_COLS + ["filing_url"] if c in h]])}


def panel_csv(rid: str) -> str:
    """Loans of the reports that passed in this run, as CSV."""
    r = _get(rid)
    ok = set(r["rec"].loc[r["rec"]["admitted"], "adsh"])
    h = r["kept"][r["kept"]["adsh"].isin(ok)]
    return h[[c for c in report.PANEL_COLS + report.SOURCE_COLUMNS + ["filing_url"] if c in h]].to_csv(index=False)


LOAN_COLS = ["name", "identifier", "industry", "investment_type", "is_debt", "fair_value", "principal",
             "price", "price_status", "check_currency", "interest_rate", "spread", "maturity", "release", "adsh",
             "source_rows", "in_final", "filing_url"] + report.SOURCE_COLUMNS


def _loans(rid, q=None, scope="final", debt_only=False, industries=None, min_fv=None,
           price_lo=None, price_hi=None) -> pd.DataFrame:
    h = _get(rid)["kept"]
    if scope == "final":
        h = h[h["in_final"]]
    if q:
        text = (h["identifier"].fillna("") + " " + h["name"].fillna("") + " "
                + h["industry"].fillna("")).str.lower()
        mask = pd.Series(True, index=h.index)
        for term in q.lower().split():
            mask &= text.str.contains(term, regex=False)
        h = h[mask]
    if debt_only:
        h = h[h["is_debt"].astype(bool)]
    if industries:
        h = h[h["industry"].isin(industries)]
    if min_fv is not None:
        h = h[h["fair_value"].ge(min_fv)]
    if price_lo is not None:
        h = h[h["price"].ge(price_lo)]
    if price_hi is not None:
        h = h[h["price"].lt(price_hi)]
    return h


def loans(rid, limit=2000, **filters) -> dict:
    """Loans matching a search, with a per-fund summary (how each fund values them)."""
    h = _loans(rid, **filters)
    by_fund = (h.groupby(["name", "adsh"], dropna=False)
               .agg(loans=("identifier", "size"), fair_value=("fair_value", "sum"),
                    principal=("principal", "sum"), avg_price=("price", "mean"),
                    in_final=("in_final", "first"))
               .reset_index().sort_values("fair_value", ascending=False))
    by_fund["principal"] = float("nan")  # unknown currencies/units cannot be summed
    by_fund["avg_price"] = by_fund["avg_price"].round(1)
    rows = h.sort_values("fair_value", ascending=False).head(limit)
    return {"count": int(len(h)), "funds": int(h["adsh"].nunique()),
            "fair_value": float(h["fair_value"].sum()), "truncated": bool(len(h) > limit),
            "by_fund": records(by_fund.head(300)),
            "loans": records(rows[[c for c in LOAN_COLS if c in rows]])}


def loans_csv(rid, **filters) -> str:
    h = _loans(rid, **filters).sort_values("fair_value", ascending=False)
    return h[[c for c in LOAN_COLS if c in h]].to_csv(index=False)


def overview(rid) -> dict:
    """Quick picture of the final list."""
    h = _loans(rid)
    total = float(h["fair_value"].sum())
    ind = (h.groupby(h["industry"].fillna("(not given)"))["fair_value"].sum()
           .sort_values(ascending=False).rename("fair_value").reset_index())
    funds = (h.groupby("name")["fair_value"].sum().sort_values(ascending=False)
             .rename("fair_value").reset_index())
    return {"loans": int(len(h)), "funds": int(h["adsh"].nunique()), "fair_value": total,
            "debt_share": float(h.loc[h["is_debt"].astype(bool), "fair_value"].sum() / total) if total else 0.0,
            "below_90": None, "price_status": "unverified principal currency/units", "check_currency": int(h["check_currency"].sum()),
            "industries": records(ind.head(15)), "funds_top": records(funds.head(15)),
            "all_industries": sorted(_get(rid)["kept"]["industry"].dropna().unique().tolist())}


def sample(rid: str, n_largest=5, n_random=5, per_filing=2, seed=7) -> list:
    """Same draw as scripts/spot_check_sample.py, on this run's admitted filings."""
    r = _get(rid)
    ok = set(r["rec"].loc[r["rec"]["admitted"], "adsh"])
    panel = r["kept"][r["kept"]["adsh"].isin(ok)]
    if panel.empty:
        return []
    from lookthrough.sampling import select_sample
    picked = select_sample(panel, seed=seed, n_largest=n_largest,
                           n_random=n_random, per_filing=per_filing)
    return records(picked[SAMPLE_COLS])


def reviewed_spot_checks() -> list:
    p = ROOT / P["outputs"]["reports"] / "spot_check.csv"
    if not p.exists():
        return []
    return records(pd.read_csv(p, dtype=str, keep_default_na=False))