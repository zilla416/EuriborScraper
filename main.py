"""
main.py – FastAPI application for the Euribor Rates API.

Endpoints
─────────
GET /                       Info & available endpoints
GET /rates/latest           Most recent rate for all terms
GET /rates                  All historical rates grouped by term
GET /rates/{term}           All historical rates for one term (1w|1m|3m|6m|12m)
GET /rates/{term}/{year}    Rates for a specific term and calendar year
GET /rates/year/{year}      All terms for a specific calendar year
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from scraper import (
    VALID_TERMS,
    START_YEAR,
    get_all_rates,
    get_latest_rates,
    get_rates_for_term,
    get_rates_for_term_year,
    get_rates_for_year,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Euribor Rates API",
    description=(
        "Fetches historical and current Euribor rates from euriborrates.com "
        "and returns them as structured JSON. "
        "Data is scraped from HTML tables and cached server-side."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

CURRENT_YEAR = datetime.now().year


def _validate_term(term: str) -> str:
    t = term.lower()
    if t not in VALID_TERMS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid term '{term}'. Must be one of: {', '.join(VALID_TERMS)}",
        )
    return t


def _validate_year(year: int) -> int:
    if year < START_YEAR or year > CURRENT_YEAR:
        raise HTTPException(
            status_code=422,
            detail=f"Year must be between {START_YEAR} and {CURRENT_YEAR}.",
        )
    return year


def _ok(data: Any, meta: dict | None = None) -> JSONResponse:
    body: dict = {"success": True, "data": data}
    if meta:
        body["meta"] = meta
    return JSONResponse(body)


# ─── Routes ──────────────────────────────────────────────────────────────────


@app.get("/", summary="API info")
async def root() -> JSONResponse:
    return _ok(
        {
            "name": "Euribor Rates API",
            "version": "1.0.0",
            "source": "https://euriborrates.com",
            "available_terms": VALID_TERMS,
            "data_start_year": START_YEAR,
            "endpoints": {
                "GET /rates/latest": "Most recent rate for each term",
                "GET /rates": "All historical rates grouped by term",
                "GET /rates/{term}": "All historical rates for one term",
                "GET /rates/{term}/{year}": "Rates for a term/year combination",
                "GET /rates/year/{year}": "All terms for a calendar year",
            },
        }
    )


@app.get("/rates/latest", summary="Latest rate for each term")
async def latest_rates() -> JSONResponse:
    """Returns the most recent published rate for every Euribor term."""
    data = await get_latest_rates()
    return _ok(
        data,
        meta={"count": len(data), "fetched_at": datetime.utcnow().isoformat() + "Z"},
    )


@app.get("/rates", summary="All historical rates (all terms)")
async def all_rates(
    term: str | None = Query(
        default=None,
        description="Filter by term (1w, 1m, 3m, 6m, 12m)",
    )
) -> JSONResponse:
    """
    Returns the complete historical dataset grouped by term.
    Optionally filter with ?term=3m.

    ⚠️ This endpoint fetches data from 1999 → today across all terms.
    It may take 10-30 seconds on a cold start (no cache).
    """
    if term is not None:
        t = _validate_term(term)
        data = await get_rates_for_term(t)
        return _ok(
            {t: data},
            meta={
                "term": t,
                "count": len(data),
                "fetched_at": datetime.utcnow().isoformat() + "Z",
            },
        )

    data = await get_all_rates()
    total = sum(len(v) for v in data.values())
    return _ok(
        data,
        meta={
            "total_records": total,
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        },
    )


@app.get("/rates/year/{year}", summary="All terms for a specific year")
async def rates_for_year(
    year: int = Path(..., description="Calendar year (e.g. 2024)"),
) -> JSONResponse:
    """Returns all Euribor terms' data for the given calendar year."""
    yr = _validate_year(year)
    data = await get_rates_for_year(yr)
    total = sum(len(v) for v in data.values())
    return _ok(
        data,
        meta={
            "year": yr,
            "total_records": total,
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        },
    )


@app.get("/rates/{term}", summary="All historical rates for one term")
async def rates_for_term(
    term: str = Path(..., description="Euribor term: 1w | 1m | 3m | 6m | 12m"),
) -> JSONResponse:
    """
    Returns all historical daily rates for the specified term.

    ⚠️ Fetches data from 1999 → today. May take 10-30 s on a cold start.
    """
    t = _validate_term(term)
    data = await get_rates_for_term(t)
    return _ok(
        data,
        meta={
            "term": t,
            "count": len(data),
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        },
    )


@app.get("/rates/{term}/{year}", summary="Rates for a specific term and year")
async def rates_for_term_year(
    term: str = Path(..., description="Euribor term: 1w | 1m | 3m | 6m | 12m"),
    year: int = Path(..., description="Calendar year (e.g. 2024)"),
) -> JSONResponse:
    """Returns all daily rates for the given term and calendar year."""
    t = _validate_term(term)
    yr = _validate_year(year)
    data = await get_rates_for_term_year(t, yr)
    return _ok(
        data,
        meta={
            "term": t,
            "year": yr,
            "count": len(data),
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        },
    )
