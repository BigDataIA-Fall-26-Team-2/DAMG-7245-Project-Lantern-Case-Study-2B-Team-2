"""LANTERN backend: run the look-through pipeline with chosen settings.

Start from inside cs2b:  uvicorn app.api:app --port 8000
Swagger UI: http://127.0.0.1:8000/docs   ReDoc: http://127.0.0.1:8000/redoc
"""
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Path, Query, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field

from app import engine

DESCRIPTION = """
Backend of **LANTERN look-through** (DAMG 7245, Case Study 2B, Team 2).

It turns the SEC's BDC data sets into one reconciled holdings panel, using the team's
pipeline code in `src/lookthrough` (the same functions `dvc repro` runs):

1. **Source**: monthly SEC ZIPs in `data/raw`, checked against `data/manifest.json` (SHA-256).
2. **Read**: SUB, NUM, TAG and SOI combined; current period only; split rows coalesced.
3. **Clean**: the cleaning rules chosen in the request (default: `params.yaml`).
4. **Compare**: each filing's holdings vs the fund's own total in NUM; admitted within the tolerance.
5. **Explore**: search, watch list and fund checks on the admitted panel.

A **run** is one set of settings (releases, tolerance, rules). `POST /runs` returns a `run_id`;
every `/runs/{run_id}/...` endpoint reads that run. Runs live in memory and never write to
`outputs/` or `reports/`, so DVC outputs are untouched. The first run on a new set of releases
reads the raw files (minutes); later runs reuse it (seconds).
"""

TAGS = [
    {"name": "Health", "description": "Is the backend up, and reload the data from disk."},
    {"name": "Source data", "description": "Which SEC files are available and whether they match their fingerprints."},
    {"name": "Runs", "description": "Run the pipeline with chosen settings, and read its filings."},
    {"name": "Explore", "description": "Search, watch list, overview and downloads on a run's admitted panel."},
    {"name": "Hand checks", "description": "Part 4 spot checks: reviewed results and new samples."},
    {"name": "Uploads", "description": "Add or remove extra months. Saved locally in data/uploads only."},
]


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=engine.warm_up, daemon=True).start()
    yield


app = FastAPI(title="LANTERN look-through API", version="1.0.0", description=DESCRIPTION,
              openapi_tags=TAGS, lifespan=lifespan)


@app.exception_handler(Exception)
def any_error(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})


class RunIn(BaseModel):
    releases: Optional[list[str]] = Field(
        default=None, description="Monthly SEC releases to use. Default: `releases` in params.yaml.",
        examples=[["2026_04", "2026_05", "2026_06"]])
    tolerance: Optional[float] = Field(
        default=None, ge=0, lt=1,
        description="Admission tolerance as a fraction: 0.01 means a filing passes when "
                    "|our sum - fund's total| / fund's total <= 1%. Default: params.yaml.",
        examples=[0.01])
    rules: Optional[list[str]] = Field(
        default=None, description="Cleaning rules to apply, by name (see GET /config). "
                                  "Default: cleaning.rules in params.yaml. An empty list means no cleaning.",
        examples=[["rule_totals", "rule_cash", "rule_commitment_rows"]])


class SampleIn(BaseModel):
    n_largest: int = Field(default=5, ge=0, le=50, description="How many of the largest admitted filings.")
    n_random: int = Field(default=5, ge=0, le=50, description="How many more admitted filings at random.")
    per_filing: int = Field(default=2, ge=1, le=10,
                            description="Holdings per filing: the largest, plus the rest at random.")
    seed: int = Field(default=7, description="Random seed. The same seed on the same panel gives the same sample.")


class FetchIn(BaseModel):
    release: str = Field(description="Release to download from the SEC, like 2026_08 or 2025q4.",
                         examples=["2026_08"])


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except KeyError as e:
        raise HTTPException(404, f"not found: {e}")
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e))


RID = "Run id returned by POST /runs."
ADSH = "SEC accession number of one filing, like 0001736035-26-000010."


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


# ---------------------------------------------------------------- health
@app.get("/health", tags=["Health"], summary="Is the backend running")
def health():
    return {"status": "ok"}


@app.post("/refresh", tags=["Health"], summary="Reload the data from disk",
          description="Forgets every run and every loaded release, then reloads the team releases "
                      "in the background. Use after `dvc pull`, a new `data/triage.csv`, or adding a month.")
def refresh():
    out = engine.refresh()
    threading.Thread(target=engine.warm_up, daemon=True).start()
    return out


# ---------------------------------------------------------------- source data
@app.get("/config", tags=["Source data"], summary="Available releases, rules and defaults",
         description="Releases found in data/raw and data/uploads, all cleaning rule names with their "
                     "descriptions, and the defaults from params.yaml.")
def config():
    return engine.config()


@app.get("/source", tags=["Source data"], summary="SEC files and their fingerprint check",
         description="Entries of data/manifest.json (path, URL, size, SHA-256) and which files no "
                     "longer match their recorded fingerprint (empty list = all verified).")
def get_source():
    return engine.source()


# ---------------------------------------------------------------- uploads
@app.get("/releases", tags=["Uploads"], summary="All releases and where each comes from",
         description="Team releases (data/raw, DVC) and added ones (data/uploads), with origin and fingerprint.")
def get_releases():
    return engine.releases_info()


@app.post("/releases/upload", tags=["Uploads"], summary="Add a month from an uploaded ZIP",
          description="Checks the ZIP is an SEC BDC data set (soi.tsv, sub.tsv, num.tsv, tag.tsv), unpacks "
                      "it into data/uploads and records its SHA-256. Refuses names already in use.")
async def upload_release(release: str = Form(..., description="Month name, like 2026_08 or 2025q4."),
                         file: UploadFile = File(..., description="The SEC BDC data set ZIP.")):
    data = await file.read()
    return _call(engine.add_upload, release, data)


@app.post("/releases/fetch", tags=["Uploads"], summary="Add a month downloaded from the SEC",
          description="Downloads <release>_bdc.zip from the SEC with the User-Agent in params.yaml, then "
                      "checks, unpacks and fingerprints it like an upload.")
def fetch_release(body: FetchIn):
    return _call(engine.add_from_sec, body.release)


@app.delete("/releases/{release}", tags=["Uploads"], summary="Remove an added month",
            description="Deletes an added month from data/uploads. Team releases in data/raw cannot be removed.")
def delete_release(release: str):
    return _call(engine.remove_release, release)


# ---------------------------------------------------------------- runs
@app.post("/runs", tags=["Runs"], summary="Run the pipeline with chosen settings",
          description="Reads the chosen releases (cached), applies the chosen cleaning rules, reconciles "
                      "every filing with the tolerance, and returns the run id, settings, coverage, step "
                      "counts (read, clean, final) and the cleaning log. Send `{}` for the team defaults.")
def create_run(body: RunIn):
    return _call(engine.run, body.releases, body.tolerance, body.rules)


@app.get("/runs/{rid}", tags=["Runs"], summary="Summary of a run")
def get_run(rid: str = Path(..., description=RID)):
    return _call(engine.summary, rid)


@app.get("/runs/{rid}/filings", tags=["Runs"], summary="Filings of a run with their reconciliation",
         description="One row per attempted filing: our sum, the fund's own total, gap, admitted, and the "
                     "triage reason from data/triage.csv for excluded filings.")
def get_filings(rid: str, admitted: Optional[bool] = Query(None, description="Only admitted (true) or excluded (false)."),
                q: Optional[str] = Query(None, description="Fund name contains this text.")):
    return _call(engine.filings, rid, admitted, q)


@app.get("/runs/{rid}/filings/{adsh}/holdings", tags=["Runs"], summary="One filing and its holdings",
         description="The filing's reconciliation row and its kept holdings, largest first, with SOI source rows.")
def get_holdings(rid: str, adsh: str):
    return _call(engine.filing_holdings, rid, adsh)


# ---------------------------------------------------------------- explore
def _filters(q, scope, debt_only, industry, min_fv, price_lo, price_hi):
    return {"q": q, "scope": scope, "debt_only": debt_only, "industries": industry or None,
            "min_fv": min_fv, "price_lo": price_lo, "price_hi": price_hi}


Q_HELP = "Words that must all appear in the loan name, fund name or industry, like 'Snoopy'."
SCOPE_HELP = "'final' = admitted filings only (default). 'all' = also filings whose totals do not match."
PRICE_HELP = "Price = 100 x fair value / principal, debt only."


@app.get("/runs/{rid}/loans", tags=["Explore"], summary="Search holdings across all funds",
         description="Matching holdings (largest 'limit' shown) plus a per-fund summary: how many, value, "
                     "principal and average price per fund. Used for search and the watch list "
                     "(debt_only=true, price_hi=90).")
def get_loans(rid: str,
              q: Optional[str] = Query(None, description=Q_HELP),
              scope: str = Query("final", description=SCOPE_HELP),
              debt_only: bool = Query(False, description="Only loans, no equity."),
              industry: Optional[list[str]] = Query(None, description="Only these industries."),
              min_fv: Optional[float] = Query(None, description="Minimum fair value in dollars."),
              price_lo: Optional[float] = Query(None, description=PRICE_HELP + " Lower bound."),
              price_hi: Optional[float] = Query(None, description=PRICE_HELP + " Upper bound (below this)."),
              limit: int = Query(2000, description="Most holdings returned.")):
    return _call(engine.loans, rid, limit=limit,
                 **_filters(q, scope, debt_only, industry, min_fv, price_lo, price_hi))


@app.get("/runs/{rid}/loans.csv", tags=["Explore"], summary="Search results as CSV",
         response_class=PlainTextResponse, description="Same filters as /loans, all rows, as CSV.")
def get_loans_csv(rid: str, q: Optional[str] = Query(None, description=Q_HELP),
                  scope: str = Query("final", description=SCOPE_HELP), debt_only: bool = False,
                  industry: Optional[list[str]] = Query(None), min_fv: Optional[float] = None,
                  price_lo: Optional[float] = None, price_hi: Optional[float] = None):
    return PlainTextResponse(_call(engine.loans_csv, rid,
                                   **_filters(q, scope, debt_only, industry, min_fv, price_lo, price_hi)),
                             media_type="text/csv")


@app.get("/runs/{rid}/overview", tags=["Explore"], summary="Big picture of the admitted panel",
         description="Holdings, funds, total value, share in debt, biggest industries and funds.")
def get_overview(rid: str):
    return _call(engine.overview, rid)


@app.get("/runs/{rid}/panel.csv", tags=["Explore"], summary="The admitted panel as CSV",
         response_class=PlainTextResponse)
def get_panel_csv(rid: str):
    return PlainTextResponse(_call(engine.panel_csv, rid), media_type="text/csv")


# ---------------------------------------------------------------- hand checks
@app.get("/spot-checks", tags=["Hand checks"], summary="Reviewed spot checks",
         description="Rows of reports/spot_check.csv: panel values next to the values read from the filing.")
def spot_checks():
    return engine.reviewed_spot_checks()


@app.post("/runs/{rid}/sample", tags=["Hand checks"], summary="Draw a spot-check sample",
          description="Same draw as scripts/spot_check_sample.py, on this run's admitted filings.")
def draw_sample(rid: str, body: SampleIn):
    return _call(engine.sample, rid, body.n_largest, body.n_random, body.per_filing, body.seed)