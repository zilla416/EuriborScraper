"""
scraper.py – fetches and parses Euribor data from euriborrates.com HTML tables.
URL pattern: https://euriborrates.com/en/historical-euribor/{year}?term={term}
Available terms: 1w, 1m, 3m, 6m, 12m
"""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from cachetools import TTLCache
from dateutil import parser as dateparser

logger = logging.getLogger(__name__)

VALID_TERMS: list[str] = ["1w", "1m", "3m", "6m", "12m"]
BASE_URL = "https://euriborrates.com/en/historical-euribor"
START_YEAR = 1999

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_cache_lock = threading.RLock()
# Past years: cache for 24 hours (data never changes)
_historical_cache: TTLCache = TTLCache(maxsize=1000, ttl=86400)
# Current year: cache for 1 hour (updates daily)
_current_cache: TTLCache = TTLCache(maxsize=20, ttl=3600)


def _get_cache(year: int) -> TTLCache:
    return _historical_cache if year < datetime.now().year else _current_cache


def _parse_table(html: str, term: str) -> list[dict]:
    """
    Parse all <table> elements in the HTML and extract (date, rate) rows.
    Expected cell formats:
        date  : M/D/YYYY  (e.g. "1/2/2025")
        rate  : X.XXX%    (e.g. "2.736%")
    """
    soup = BeautifulSoup(html, "lxml")
    records: list[dict] = []

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) != 2:
                continue

            date_text = cells[0].get_text(strip=True)
            rate_text = cells[1].get_text(strip=True)
            if not date_text or not rate_text:
                continue

            # Parse date
            try:
                parsed_date = dateparser.parse(date_text)
                if parsed_date is None:
                    continue
                date_str = parsed_date.strftime("%Y-%m-%d")
            except Exception:
                continue

            # Parse rate – strip "%" and convert to float
            rate_clean = rate_text.replace("%", "").strip()
            try:
                rate_value = float(rate_clean)
            except ValueError:
                continue

            records.append(
                {
                    "date": date_str,
                    "term": term,
                    "rate": rate_value,
                }
            )

    return sorted(records, key=lambda r: r["date"])


async def _fetch_term_year(
    term: str,
    year: int,
    client: httpx.AsyncClient,
) -> list[dict]:
    """Fetch and parse data for one term + year.  Returns [] on failure."""
    cache = _get_cache(year)
    key = (term, year)

    with _cache_lock:
        if key in cache:
            return cache[key]  # type: ignore[return-value]

    url = f"{BASE_URL}/{year}?term={term}"
    try:
        resp = await client.get(url, headers=HEADERS, follow_redirects=True, timeout=20.0)
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("HTTP %s for %s", exc.response.status_code, url)
        return []
    except Exception as exc:
        logger.warning("Error fetching %s: %s", url, exc)
        return []

    records = _parse_table(resp.text, term)

    with _cache_lock:
        cache[key] = records

    return records


# ─── Public API ──────────────────────────────────────────────────────────────


async def get_rates_for_term(term: str) -> list[dict]:
    """Return all historical daily rates for *term* (1999 → today)."""
    current_year = datetime.now().year
    years = list(range(START_YEAR, current_year + 1))

    all_records: list[dict] = []
    async with httpx.AsyncClient() as client:
        # Process in batches of 5 to be polite to the source server
        batch_size = 5
        for i in range(0, len(years), batch_size):
            batch = years[i : i + batch_size]
            results = await asyncio.gather(
                *[_fetch_term_year(term, yr, client) for yr in batch],
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, list):
                    all_records.extend(result)
            if i + batch_size < len(years):
                await asyncio.sleep(0.3)

    return sorted(all_records, key=lambda r: r["date"])


async def get_rates_for_year(year: int) -> dict[str, list[dict]]:
    """Return all terms for a specific *year*."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[_fetch_term_year(term, year, client) for term in VALID_TERMS],
            return_exceptions=True,
        )

    return {
        term: (result if isinstance(result, list) else [])
        for term, result in zip(VALID_TERMS, results)
    }


async def get_rates_for_term_year(term: str, year: int) -> list[dict]:
    """Return daily rates for a specific *term* + *year*."""
    async with httpx.AsyncClient() as client:
        return await _fetch_term_year(term, year, client)


async def get_latest_rates() -> list[dict]:
    """Return the single most-recent rate entry for every term."""
    current_year = datetime.now().year
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[_fetch_term_year(term, current_year, client) for term in VALID_TERMS],
            return_exceptions=True,
        )

    latest: list[dict] = []
    for term, result in zip(VALID_TERMS, results):
        if isinstance(result, list) and result:
            latest.append(result[-1])

    return latest


async def get_all_rates() -> dict[str, list[dict]]:
    """Return all historical rates for *every* term."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[
                asyncio.create_task(get_rates_for_term(term))
                for term in VALID_TERMS
            ],
            return_exceptions=True,
        )

    return {
        term: (result if isinstance(result, list) else [])
        for term, result in zip(VALID_TERMS, results)
    }
