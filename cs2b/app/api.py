"""LANTERN backend: run the look-through pipeline with chosen settings.

Start from inside cs2b:  uvicorn app.api:app --port 8000
"""
import threading
from typing import Optional

from fastapi import Query

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app import engine

app = FastAPI(title="LANTERN look-through API")


@app.on_event("startup")
def start_warm_up():
    threading.Thread(target=engine.warm_up, daemon=True).start()


@app.exception_handler(Exception)
def any_error(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})


class RunIn(BaseModel):
    releases: Optional[list[str]] = None
    tolerance: Optional[float] = Field(default=None, ge=0, lt=1)
    rules: Optional[list[str]] = None


class SampleIn(BaseModel):
    n_largest: int = Field(default=5, ge=0, le=50)
    n_random: int = Field(default=5, ge=0, le=50)
    per_filing: int = Field(default=2, ge=1, le=10)
    seed: int = 7


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except KeyError as e:
        raise HTTPException(404, f"not found: {e}")
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/refresh")
def refresh():
    out = engine.refresh()
    threading.Thread(target=engine.warm_up, daemon=True).start()
    return out


@app.get("/config")
def config():
    return engine.config()


@app.get("/source")
def get_source():
    return engine.source()


@app.get("/releases")
def get_releases():
    return engine.releases_info()


@app.post("/releases/upload")
async def upload_release(release: str = Form(...), file: UploadFile = File(...)):
    data = await file.read()
    return _call(engine.add_upload, release, data)


class FetchIn(BaseModel):
    release: str


@app.post("/releases/fetch")
def fetch_release(body: FetchIn):
    return _call(engine.add_from_sec, body.release)


@app.delete("/releases/{release}")
def delete_release(release: str):
    return _call(engine.remove_release, release)


@app.post("/runs")
def create_run(body: RunIn):
    return _call(engine.run, body.releases, body.tolerance, body.rules)


@app.get("/runs/{rid}")
def get_run(rid: str):
    return _call(engine.summary, rid)


@app.get("/runs/{rid}/filings")
def get_filings(rid: str, admitted: Optional[bool] = None, q: Optional[str] = None):
    return _call(engine.filings, rid, admitted, q)


@app.get("/runs/{rid}/filings/{adsh}/holdings")
def get_holdings(rid: str, adsh: str):
    return _call(engine.filing_holdings, rid, adsh)


@app.get("/runs/{rid}/panel.csv", response_class=PlainTextResponse)
def get_panel_csv(rid: str):
    return PlainTextResponse(_call(engine.panel_csv, rid), media_type="text/csv")


def _filters(q, scope, debt_only, industry, min_fv, price_lo, price_hi):
    return {"q": q, "scope": scope, "debt_only": debt_only, "industries": industry or None,
            "min_fv": min_fv, "price_lo": price_lo, "price_hi": price_hi}


@app.get("/runs/{rid}/loans")
def get_loans(rid: str, q: Optional[str] = None, scope: str = "final", debt_only: bool = False,
              industry: Optional[list[str]] = Query(None), min_fv: Optional[float] = None,
              price_lo: Optional[float] = None, price_hi: Optional[float] = None, limit: int = 2000):
    return _call(engine.loans, rid, limit=limit,
                 **_filters(q, scope, debt_only, industry, min_fv, price_lo, price_hi))


@app.get("/runs/{rid}/loans.csv", response_class=PlainTextResponse)
def get_loans_csv(rid: str, q: Optional[str] = None, scope: str = "final", debt_only: bool = False,
                  industry: Optional[list[str]] = Query(None), min_fv: Optional[float] = None,
                  price_lo: Optional[float] = None, price_hi: Optional[float] = None):
    return PlainTextResponse(_call(engine.loans_csv, rid,
                                   **_filters(q, scope, debt_only, industry, min_fv, price_lo, price_hi)),
                             media_type="text/csv")


@app.get("/runs/{rid}/overview")
def get_overview(rid: str):
    return _call(engine.overview, rid)


@app.post("/runs/{rid}/sample")
def draw_sample(rid: str, body: SampleIn):
    return _call(engine.sample, rid, body.n_largest, body.n_random, body.per_filing, body.seed)


@app.get("/spot-checks")
def spot_checks():
    return engine.reviewed_spot_checks()