from __future__ import annotations

import asyncio
import datetime

import httpx
from loguru import logger

from ..config import Config
from ..models import PaperRecord

BASE_URL = "https://ntrs.nasa.gov/api/citations/search"


# Track whether NTRS has been confirmed unreachable this session
_ntrs_unavailable: bool = False


async def search(query: str, config: Config) -> list[PaperRecord]:
    global _ntrs_unavailable
    if _ntrs_unavailable:
        return []

    db = config.db_by_name("NASA Technical Reports Server")
    max_results = db.max_results_per_query if db else 100

    records: list[PaperRecord] = []
    start = 0
    rows = min(25, max_results)

    async with httpx.AsyncClient(timeout=30.0) as client:
        while start < max_results:
            params = {
                "q": query,
                "rows": rows,
                "start": start,
            }
            data = await _fetch(client, params)
            if data is None:
                # _fetch logs the error and sets _ntrs_unavailable if appropriate
                break

            results = data.get("results", [])
            if not results:
                break

            for item in results:
                record = _normalise(item)
                if record:
                    records.append(record)

            start += len(results)
            if len(results) < rows:
                break

            await asyncio.sleep(0.5)

    logger.info(f"NASA NTRS: '{query[:60]}' → {len(records)} records")
    return records


async def _fetch(client: httpx.AsyncClient, params: dict) -> dict | None:
    global _ntrs_unavailable
    try:
        resp = await client.get(BASE_URL, params=params)
        if resp.status_code == 403:
            logger.warning(
                "NASA NTRS: 403 Forbidden — marking as unavailable for this session"
            )
            _ntrs_unavailable = True
            return None
        if resp.status_code == 429:
            logger.warning("NASA NTRS: 429 rate limited — waiting 30s")
            await asyncio.sleep(30)
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"NASA NTRS request error: {e}")
        return None


def _normalise(item: dict) -> PaperRecord | None:
    title = item.get("title", "").strip()
    if not title:
        return None

    authors_raw = item.get("authors") or []
    authors: list[str] = []
    for a in authors_raw:
        name = ""
        if isinstance(a, dict):
            name = a.get("name", "") or ""
        elif isinstance(a, str):
            name = a
        if name:
            authors.append(name)

    # Publication year from publicationDate field
    pub_date = item.get("publicationDate") or item.get("disseminated") or ""
    year: int | None = None
    if pub_date:
        try:
            year = int(str(pub_date)[:4])
        except ValueError:
            pass

    ntrs_id = str(item.get("id", "")) or None
    report_numbers = item.get("reportNumbers") or []
    venue_parts = ["NASA NTRS"]
    if report_numbers:
        venue_parts.append(
            report_numbers[0]
            if isinstance(report_numbers[0], str)
            else str(report_numbers[0])
        )
    venue = " — ".join(venue_parts)

    abstract = item.get("abstract") or None

    return PaperRecord(
        nasa_ntrs_id=ntrs_id,
        title=title,
        abstract=abstract,
        authors=authors,
        year=year,
        venue=venue,
        publication_type="Technical Report",
        source_database="NASA Technical Reports Server",
        retrieved_at=datetime.datetime.utcnow().isoformat(),
        source_type="technical_report",
    )
