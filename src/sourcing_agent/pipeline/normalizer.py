from __future__ import annotations

import datetime
import re
from typing import Any

from loguru import logger

from ..models import PaperRecord


def normalize_semantic_scholar(raw: dict[str, Any]) -> PaperRecord | None:
    title = (raw.get("title") or "").strip()
    if not title:
        logger.debug("Semantic Scholar: skipping record with no title")
        return None

    ext_ids = raw.get("externalIds") or {}
    authors_raw = raw.get("authors") or []
    authors = [a.get("name", "") for a in authors_raw if a.get("name")]

    oa_pdf = raw.get("openAccessPdf") or {}
    pdf_url = oa_pdf.get("url") if isinstance(oa_pdf, dict) else None
    pub_types = raw.get("publicationTypes") or []

    return PaperRecord(
        doi=ext_ids.get("DOI"),
        arxiv_id=ext_ids.get("ArXiv"),
        s2_paper_id=raw.get("paperId"),
        title=title,
        abstract=raw.get("abstract"),
        authors=authors,
        year=raw.get("year"),
        venue=raw.get("venue"),
        publication_type=pub_types[0] if pub_types else None,
        source_database="Semantic Scholar",
        retrieved_at=datetime.datetime.utcnow().isoformat(),
        open_access_pdf_url=pdf_url,
        citation_count=raw.get("citationCount"),
    )


def normalize_arxiv(entry: dict[str, Any]) -> PaperRecord | None:
    title = entry.get("title", "").replace("\n", " ").strip()
    if not title:
        return None

    raw_id = entry.get("id", "")
    arxiv_id: str | None = None
    if raw_id:
        m = re.search(r"abs/(.+)$", raw_id)
        arxiv_id = (m.group(1) if m else raw_id).rstrip("/") or None

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

    return PaperRecord(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=authors,
        year=year,
        venue=journal_ref,
        source_database="arXiv",
        retrieved_at=datetime.datetime.utcnow().isoformat(),
        open_access_pdf_url=pdf_url,
    )


def normalize_nasa_ntrs(item: dict[str, Any]) -> PaperRecord | None:
    title = (item.get("title") or "").strip()
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
        rn = report_numbers[0]
        venue_parts.append(rn if isinstance(rn, str) else str(rn))

    return PaperRecord(
        nasa_ntrs_id=ntrs_id,
        title=title,
        abstract=item.get("abstract") or None,
        authors=authors,
        year=year,
        venue=" — ".join(venue_parts),
        publication_type="Technical Report",
        source_database="NASA Technical Reports Server",
        retrieved_at=datetime.datetime.utcnow().isoformat(),
        source_type="technical_report",
    )


def normalize_browser(raw: dict[str, Any], source: str) -> PaperRecord | None:
    title = (raw.get("title") or "").strip()
    if not title:
        return None

    authors = raw.get("authors", [])
    if isinstance(authors, str):
        authors = [a.strip() for a in re.split(r"[;,]", authors) if a.strip()]

    year_raw = raw.get("year")
    year: int | None = None
    if year_raw:
        try:
            year = int(str(year_raw)[:4])
        except ValueError:
            pass

    return PaperRecord(
        doi=raw.get("doi"),
        title=title,
        abstract=raw.get("abstract"),
        authors=authors,
        year=year,
        venue=raw.get("venue"),
        source_database=source,
        retrieved_at=datetime.datetime.utcnow().isoformat(),
    )
