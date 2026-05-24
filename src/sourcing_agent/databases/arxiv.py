from __future__ import annotations

import asyncio
import datetime
import re

import feedparser
import httpx
from loguru import logger

from ..config import Config
from ..models import PaperRecord

BASE_URL = "https://export.arxiv.org/api/query"
CATEGORIES = ["cs.RO", "cs.AI", "cs.LG", "cs.SY"]


async def search(query: str, config: Config) -> list[PaperRecord]:
    db = config.db_by_name("arXiv")
    max_results = db.max_results_per_query if db else 150

    cat_filter = " OR ".join(f"cat:{c}" for c in CATEGORIES)
    full_query = f"({query}) AND ({cat_filter})"

    records: list[PaperRecord] = []
    start = 0
    batch_size = min(50, max_results)

    async with httpx.AsyncClient(timeout=30.0) as client:
        while start < max_results:
            params: dict[str, str | int] = {
                "search_query": full_query,
                "start": start,
                "max_results": batch_size,
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
            try:
                resp = await client.get(BASE_URL, params=params)
                resp.raise_for_status()
            except Exception as e:
                logger.error(f"arXiv request error: {e}")
                break

            feed = feedparser.parse(resp.text)
            entries = feed.get("entries", [])
            if not entries:
                break

            for entry in entries:
                record = _normalise(entry)
                if record:
                    records.append(record)

            start += len(entries)
            if len(entries) < batch_size:
                break

            await asyncio.sleep(0.5)

    logger.info(f"arXiv: '{query[:60]}' → {len(records)} records")
    return records


def _normalise(entry: dict) -> PaperRecord | None:
    title = entry.get("title", "").replace("\n", " ").strip()
    if not title:
        return None

    arxiv_id = ""
    raw_id = entry.get("id", "")
    if raw_id:
        # Strip URL prefix, keep e.g. 2301.12345 or 2301.12345v2
        match = re.search(r"abs/(.+)$", raw_id)
        arxiv_id = match.group(1) if match else raw_id
        arxiv_id = arxiv_id.rstrip("/")

    authors = [a.get("name", "") for a in entry.get("authors", []) if a.get("name")]

    published = entry.get("published", "")
    year: int | None = None
    if published:
        try:
            year = int(published[:4])
        except ValueError:
            pass

    abstract = entry.get("summary", "").replace("\n", " ").strip() or None

    journal_ref = entry.get("arxiv_journal_ref") or None

    pdf_url: str | None = None
    for link in entry.get("links", []):
        if link.get("type") == "application/pdf":
            pdf_url = link.get("href")
            break

    # Try to extract DOI from journal ref or tags
    doi: str | None = None
    for tag in entry.get("tags", []):
        term = tag.get("term", "")
        if "doi" in term.lower():
            doi = term
            break

    return PaperRecord(
        arxiv_id=arxiv_id or None,
        doi=doi,
        title=title,
        abstract=abstract,
        authors=authors,
        year=year,
        venue=journal_ref,
        source_database="arXiv",
        retrieved_at=datetime.datetime.utcnow().isoformat(),
        open_access_pdf_url=pdf_url,
    )
