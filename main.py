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
from fastapi.responses import HTMLResponse, JSONResponse

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
    docs_url=None,
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


# ─── Custom Swagger UI with dark-mode toggle ─────────────────────────────────

_SWAGGER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Euribor Rates API – Swagger UI</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
  <style>
    /* ── Toggle button ── */
    #dm-toggle {
      position: fixed;
      top: 14px;
      right: 20px;
      z-index: 9999;
      padding: 6px 14px;
      border-radius: 20px;
      border: 1px solid #ccc;
      background: #fff;
      color: #333;
      font-size: 13px;
      font-family: sans-serif;
      cursor: pointer;
      box-shadow: 0 2px 6px rgba(0,0,0,.15);
      transition: background .2s, color .2s;
    }
    #dm-toggle:hover { background: #f0f0f0; }

    /* ── Dark mode: invert the whole UI, then re-invert images/code ── */
    body.dm { background: #1a1a2e; }
    body.dm .swagger-ui {
      filter: invert(88%) hue-rotate(180deg);
    }
    body.dm .swagger-ui img,
    body.dm .swagger-ui svg.svg-assets,
    body.dm .swagger-ui .highlight-code,
    body.dm .swagger-ui .microlight {
      filter: invert(100%) hue-rotate(180deg);
    }
    body.dm #dm-toggle {
      background: #2e2e4e;
      color: #ddd;
      border-color: #555;
    }
    body.dm #dm-toggle:hover { background: #3a3a5e; }
  </style>
</head>
<body>
  <button id="dm-toggle">&#127769; Dark mode</button>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
  <script>
    SwaggerUIBundle({
      url: "/openapi.json",
      dom_id: "#swagger-ui",
      deepLinking: true,
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
      plugins: [SwaggerUIBundle.plugins.DownloadUrl],
      layout: "StandaloneLayout"
    });

    const btn = document.getElementById("dm-toggle");
    const apply = (dark) => {
      document.body.classList.toggle("dm", dark);
      btn.innerHTML = dark ? "&#9728;&#65039; Light mode" : "&#127769; Dark mode";
    };
    apply(localStorage.getItem("euribor-dm") === "1");
    btn.addEventListener("click", () => {
      const next = !document.body.classList.contains("dm");
      apply(next);
      localStorage.setItem("euribor-dm", next ? "1" : "0");
    });
  </script>
</body>
</html>
"""


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui() -> HTMLResponse:
    return HTMLResponse(_SWAGGER_HTML)


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
