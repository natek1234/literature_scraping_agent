from __future__ import annotations

import asyncio
import datetime
import os

import httpx
from loguru import logger

from ..config import Config
from ..models import PaperRecord

BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = (
    "paperId,title,abstract,authors,year,venue,"
    "citationCount,isOpenAccess,openAccessPdf,"
    "externalIds,publicationTypes"
)


async def search(query: str, config: Config) -> list[PaperRecord]:
    db = config.db_by_name("Semantic Scholar")
    max_results = db.max_results_per_query if db else 200

    headers: dict[str, str] = {}
    if api_key := os.environ.get("S2_API_KEY"):
        headers["x-api-key"] = api_key
        rate_limit_delay = 0.05  # 100 req/sec with key
    else:
        rate_limit_delay = 3.0  # ~10 req/min without key to avoid 429

    records: list[PaperRecord] = []
    offset = 0
    limit = min(100, max_results)

    async with httpx.AsyncClient(timeout=30.0) as client:
        while offset < max_results:
            params = {
                "query": query,
                "fields": FIELDS,
                "limit": limit,
                "offset": offset,
            }
            response = await _fetch_with_retry(client, params, headers)
            if response is None:
                break

            data = response.json()
            batch = data.get("data", [])
            if not batch:
                break

            for paper in batch:
                record = _normalise(paper)
                if record:
                    records.append(record)

            total = data.get("total", 0)
            offset += len(batch)
            if offset >= total or offset >= max_results:
                break

            await asyncio.sleep(rate_limit_delay)

    logger.info(f"Semantic Scholar: '{query[:60]}' → {len(records)} records")
    return records


async def _fetch_with_retry(
    client: httpx.AsyncClient,
    params: dict,
    headers: dict,
) -> httpx.Response | None:
    for attempt in range(5):
        try:
            resp = await client.get(BASE_URL, params=params, headers=headers)
            if resp.status_code == 429:
                wait = min(30 * (2**attempt), 120)
                logger.warning(
                    f"Semantic Scholar: 429 rate limit — waiting {wait}s (attempt {attempt+1})"
                )
                await asyncio.sleep(wait)
                continue
            if resp.status_code == 403:
                logger.warning("Semantic Scholar: 403 — query rejected, skipping")
                return None
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            logger.error(f"Semantic Scholar HTTP error {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Semantic Scholar request error: {e}")
            return None
    logger.error("Semantic Scholar: max retries reached")
    return None


def _normalise(paper: dict) -> PaperRecord | None:
    title = paper.get("title") or ""
    if not title:
        return None

    ext_ids = paper.get("externalIds") or {}
    authors_raw = paper.get("authors") or []
    authors = [a.get("name", "") for a in authors_raw if a.get("name")]

    oa_pdf = paper.get("openAccessPdf") or {}
    pdf_url = oa_pdf.get("url") if isinstance(oa_pdf, dict) else None

    pub_types = paper.get("publicationTypes") or []
    pub_type = pub_types[0] if pub_types else None

    return PaperRecord(
        doi=ext_ids.get("DOI"),
        arxiv_id=ext_ids.get("ArXiv"),
        s2_paper_id=paper.get("paperId"),
        title=title,
        abstract=paper.get("abstract"),
        authors=authors,
        year=paper.get("year"),
        venue=paper.get("venue"),
        publication_type=pub_type,
        source_database="Semantic Scholar",
        retrieved_at=datetime.datetime.utcnow().isoformat(),
        open_access_pdf_url=pdf_url,
        citation_count=paper.get("citationCount"),
    )
