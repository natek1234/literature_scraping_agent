"""Integration tests for the arXiv database client.

Run with:  pytest tests/databases/test_arxiv.py -v -m integration
These tests hit the real arXiv API and require network access.
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

_BASE_URL = "https://export.arxiv.org/api/query"
_QUERY = "autonomous robot navigation SLAM"


# ── Connectivity ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_arxiv_api_reachable() -> None:
    """arXiv export API responds with HTTP 200 to a basic search."""
    params = {"search_query": f"all:{_QUERY}", "max_results": 1}

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            resp = await client.get(_BASE_URL, params=params)
        except httpx.ConnectError as exc:
            pytest.fail(
                f"Cannot reach arXiv API.\n"
                f"  URL   : {_BASE_URL}\n"
                f"  Cause : {exc}\n"
                f"  Check : network connectivity, DNS, and firewall rules.\n"
                f"  Verify: curl '{_BASE_URL}?search_query=all:robot&max_results=1'"
            )
        except httpx.TimeoutException as exc:
            pytest.fail(
                f"arXiv API timed out after 30 s.\n"
                f"  URL   : {_BASE_URL}\n"
                f"  Cause : {exc}\n"
                f"  Check : network latency or arXiv service status."
            )

    assert resp.status_code == 200, (
        f"arXiv API returned HTTP {resp.status_code} (expected 200).\n"
        f"  URL      : {resp.url}\n"
        f"  Response : {resp.text[:400]}"
    )


@pytest.mark.asyncio
async def test_arxiv_response_is_atom_xml() -> None:
    """arXiv response is valid Atom XML that feedparser can parse."""
    import feedparser

    params = {"search_query": f"all:{_QUERY}", "max_results": 2}

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(_BASE_URL, params=params)

    assert resp.status_code == 200, (
        f"Expected HTTP 200, got {resp.status_code}.\n"
        f"Response body: {resp.text[:400]}"
    )

    feed = feedparser.parse(resp.text)
    assert feed.get("feed"), (
        "feedparser could not parse the arXiv response as Atom XML.\n"
        f"  Content-Type : {resp.headers.get('content-type')}\n"
        f"  Body (first 400 chars): {resp.text[:400]}"
    )


# ── search() function ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.live
async def test_arxiv_search_returns_records(config) -> None:
    """search() returns a non-empty list of PaperRecord objects."""
    from sourcing_agent.databases.arxiv import search
    from sourcing_agent.models import PaperRecord

    records = await search(_QUERY, config)

    assert len(records) > 0, (
        f"arXiv search returned 0 records for query '{_QUERY}'.\n"
        f"  Expected: at least 1 PaperRecord.\n"
        f"  Check: the query is not empty and the arXiv API is reachable.\n"
        f"  Hint : run test_arxiv_api_reachable first to confirm connectivity."
    )
    assert all(isinstance(r, PaperRecord) for r in records), (
        "Not all items returned by search() are PaperRecord instances.\n"
        f"  Types found: { {type(r).__name__ for r in records} }"
    )


@pytest.mark.asyncio
@pytest.mark.live
async def test_arxiv_records_have_required_fields(config) -> None:
    """Every record has a non-empty title and source_database = 'arXiv'."""
    from sourcing_agent.databases.arxiv import search

    records = await search(_QUERY, config)

    if not records:
        pytest.skip("No records returned — run test_arxiv_search_returns_records first")

    missing_title = [r for r in records if not r.title]
    assert not missing_title, (
        f"{len(missing_title)} record(s) have an empty title.\n"
        f"  Example: {missing_title[0].model_dump() if missing_title else ''}"
    )

    wrong_source = [r for r in records if r.source_database != "arXiv"]
    assert not wrong_source, (
        f"{len(wrong_source)} record(s) have source_database != 'arXiv'.\n"
        f"  Values found: { {r.source_database for r in wrong_source} }"
    )


@pytest.mark.asyncio
@pytest.mark.live
async def test_arxiv_records_have_arxiv_ids(config) -> None:
    """Most records should carry an arxiv_id (e.g. '2301.12345')."""
    from sourcing_agent.databases.arxiv import search

    records = await search(_QUERY, config)

    if not records:
        pytest.skip("No records returned")

    with_id = [r for r in records if r.arxiv_id]
    pct = len(with_id) / len(records) * 100

    assert pct >= 80, (
        f"Only {pct:.0f}% of records have an arxiv_id (expected >= 80%).\n"
        f"  Total: {len(records)}   With ID: {len(with_id)}\n"
        f"  This may indicate a parsing regression in databases/arxiv.py."
    )


@pytest.mark.asyncio
async def test_arxiv_category_filter_applied(config) -> None:
    """Results should be in the robotics/AI categories (cs.RO, cs.AI, cs.LG, cs.SY)."""
    import feedparser

    allowed = {"cs.RO", "cs.AI", "cs.LG", "cs.SY"}
    cat_filter = " OR ".join(f"cat:{c}" for c in allowed)
    full_query = f"({_QUERY}) AND ({cat_filter})"

    params = {"search_query": full_query, "max_results": 5}
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(_BASE_URL, params=params)

    assert resp.status_code == 200
    feed = feedparser.parse(resp.text)
    entries = feed.get("entries", [])

    assert len(entries) > 0, (
        f"Category-filtered query returned 0 results.\n"
        f"  Query: {full_query}\n"
        f"  This means arXiv has no papers in {allowed} matching '{_QUERY}'."
    )


@pytest.mark.asyncio
@pytest.mark.live
async def test_arxiv_abstracts_populated(config) -> None:
    """A large majority of records should have non-empty abstracts."""
    from sourcing_agent.databases.arxiv import search

    records = await search(_QUERY, config)

    if not records:
        pytest.skip("No records returned")

    with_abstract = [r for r in records if r.abstract]
    pct = len(with_abstract) / len(records) * 100

    assert pct >= 90, (
        f"Only {pct:.0f}% of records have an abstract (expected >= 90%).\n"
        f"  Total: {len(records)}   With abstract: {len(with_abstract)}\n"
        f"  Abstracts are critical for scoring — check the normaliser."
    )
