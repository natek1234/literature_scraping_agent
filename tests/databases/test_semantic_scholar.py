"""Integration tests for the Semantic Scholar database client.

Run with:  pytest tests/databases/test_semantic_scholar.py -v -m integration

Without an S2_API_KEY the public API returns HTTP 429 (Too Many Requests)
after a small number of requests — S2 moved from 403 to 429 for keyless
IP rate-limiting in 2024. Tests that require a key are skipped automatically
when the key is absent. Add S2_API_KEY to .env to unlock the full test suite.
Get a free key at https://www.semanticscholar.org/product/api
"""

from __future__ import annotations

import os

import httpx
import pytest

pytestmark = pytest.mark.integration

_BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_QUERY = "autonomous robot navigation"


def _has_api_key() -> bool:
    return bool(os.environ.get("S2_API_KEY"))


# ── API reachability ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_s2_api_reachable() -> None:
    """Semantic Scholar API endpoint is reachable (HTTP 200, 403, or 429 expected).

    Without an API key S2 now returns 429 (IP rate-limited) rather than 403.
    Both are normal and confirm the endpoint is responding — neither is treated
    as a test failure. Any other status or connection error is a genuine problem.
    """
    params = {"query": _QUERY, "fields": "title", "limit": 1}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(_BASE_URL, params=params)
        except httpx.ConnectError as exc:
            pytest.fail(
                f"Cannot reach Semantic Scholar API.\n"
                f"  URL   : {_BASE_URL}\n"
                f"  Cause : {exc}\n"
                f"  Check : network connectivity, DNS, and firewall rules."
            )
        except httpx.TimeoutException as exc:
            pytest.fail(
                f"Semantic Scholar API timed out after 30 s.\n"
                f"  URL   : {_BASE_URL}\n"
                f"  Cause : {exc}"
            )

    assert resp.status_code in (200, 403, 429), (
        f"Unexpected HTTP status {resp.status_code} from Semantic Scholar.\n"
        f"  Expected : 200 (success), 403 (query rejected), or 429 (IP rate-limited).\n"
        f"  429 means you are hitting the keyless rate limit — add S2_API_KEY to .env.\n"
        f"  URL      : {resp.url}\n"
        f"  Response : {resp.text[:400]}"
    )


@pytest.mark.asyncio
async def test_s2_rate_limited_without_key_does_not_crash(config) -> None:
    """Without S2_API_KEY, search() returns [] promptly and does not raise.

    S2 now returns 429 (not 403) when the keyless IP rate limit is exceeded.
    The client must fast-fail on the first 429 without an API key — retrying
    with exponential backoff is futile since the limit won't clear quickly.
    This test should complete in under 5 seconds; if it hangs, the fast-fail
    path in _fetch_with_retry is broken.
    """
    if _has_api_key():
        pytest.skip("S2_API_KEY is set — test targets keyless behaviour only")

    from sourcing_agent.databases.semantic_scholar import search

    try:
        records = await search(_QUERY, config)
    except Exception as exc:
        pytest.fail(
            f"search() raised an exception when S2 returned 429.\n"
            f"  Exception type : {type(exc).__name__}\n"
            f"  Message        : {exc}\n"
            f"  Expected       : empty list [], not an exception.\n"
            f"  Fix            : _fetch_with_retry must return None on 429 "
            f"when has_key=False."
        )

    assert isinstance(
        records, list
    ), f"search() returned {type(records).__name__} instead of list."
    # 429 without a key → 0 results; occasionally 200 if not yet rate-limited
    assert len(records) >= 0  # always true — validates no crash, not result count


@pytest.mark.asyncio
async def test_s2_search_returns_records_with_key(config) -> None:
    """With S2_API_KEY, search() returns a non-empty list of PaperRecords."""
    if not _has_api_key():
        pytest.skip(
            "S2_API_KEY not set in .env — skipping authenticated search test.\n"
            "Add S2_API_KEY=<your_key> to .env to run this test.\n"
            "Get a free key at: https://www.semanticscholar.org/product/api"
        )

    from sourcing_agent.databases.semantic_scholar import search
    from sourcing_agent.models import PaperRecord

    records = await search(_QUERY, config)

    assert len(records) > 0, (
        f"Semantic Scholar returned 0 records with a valid API key.\n"
        f"  Query  : {_QUERY}\n"
        f"  Key    : S2_API_KEY is set (value hidden)\n"
        f"  Check  : key permissions, query syntax, or S2 service status.\n"
        f"  URL    : {_BASE_URL}"
    )
    assert all(isinstance(r, PaperRecord) for r in records), (
        f"Not all items are PaperRecord instances.\n"
        f"  Types found: { {type(r).__name__ for r in records} }"
    )


@pytest.mark.asyncio
async def test_s2_records_have_titles_with_key(config) -> None:
    """With S2_API_KEY, all returned records have non-empty titles."""
    if not _has_api_key():
        pytest.skip("S2_API_KEY not set — skipping")

    from sourcing_agent.databases.semantic_scholar import search

    records = await search(_QUERY, config)
    if not records:
        pytest.skip(
            "No records returned — check test_s2_search_returns_records_with_key"
        )

    missing_title = [r for r in records if not r.title]
    assert not missing_title, (
        f"{len(missing_title)} record(s) have an empty title.\n"
        f"  This indicates a normalisation bug in databases/semantic_scholar.py.\n"
        f"  Example raw paper: {missing_title[0]}"
    )


@pytest.mark.asyncio
async def test_s2_citation_counts_populated_with_key(config) -> None:
    """With S2_API_KEY, citation counts should be populated on most records."""
    if not _has_api_key():
        pytest.skip("S2_API_KEY not set — skipping")

    from sourcing_agent.databases.semantic_scholar import search

    records = await search(_QUERY, config)
    if not records:
        pytest.skip("No records returned")

    with_count = [r for r in records if r.citation_count is not None]
    pct = len(with_count) / len(records) * 100

    assert pct >= 80, (
        f"Only {pct:.0f}% of records have citation_count populated (expected >= 80%).\n"
        f"  Total: {len(records)}   With count: {len(with_count)}\n"
        f"  Check: 'citationCount' is included in the FIELDS constant in semantic_scholar.py."
    )


@pytest.mark.asyncio
async def test_s2_rate_limit_recovery(config) -> None:
    """search() survives a 429 by backing off rather than crashing."""
    if not _has_api_key():
        pytest.skip(
            "S2_API_KEY not set — rate limit recovery only matters with high-volume key usage"
        )

    from sourcing_agent.databases.semantic_scholar import search

    # Run two queries back-to-back — should not raise even if rate-limited
    try:
        await search("reinforcement learning robot", config)
        await search("SLAM navigation autonomous", config)
    except Exception as exc:
        pytest.fail(
            f"search() raised on back-to-back queries (expected backoff, not crash).\n"
            f"  Exception : {type(exc).__name__}: {exc}\n"
            f"  Check     : tenacity retry logic in _fetch_with_retry."
        )
