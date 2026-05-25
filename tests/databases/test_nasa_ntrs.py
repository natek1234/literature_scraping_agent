"""Integration tests for the NASA Technical Reports Server (NTRS) client.

Run with:  pytest tests/databases/test_nasa_ntrs.py -v -m integration

NTRS is a public, credential-free API. On some networks it returns HTTP 403
(geographic or IP block). Tests that require a successful 200 response are
skipped automatically when a 403 is detected, so the suite stays green even
on blocked networks.
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

_BASE_URL = "https://ntrs.nasa.gov/api/citations/search"
_QUERY = "Mars rover autonomy"


# ── Connectivity ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ntrs_api_reachable() -> None:
    """NTRS REST API endpoint is reachable (HTTP 200 or 403 expected).

    A 403 indicates a network/geographic block, not a client bug. Any
    other status or connection failure is a genuine problem.
    """
    params = {"q": _QUERY, "rows": 1}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(_BASE_URL, params=params)
        except httpx.ConnectError as exc:
            pytest.fail(
                f"Cannot reach NASA NTRS API.\n"
                f"  URL   : {_BASE_URL}\n"
                f"  Cause : {exc}\n"
                f"  Check : network connectivity, DNS, and firewall rules.\n"
                f"  Note  : NTRS is blocked on some corporate/university networks."
            )
        except httpx.TimeoutException as exc:
            pytest.fail(
                f"NASA NTRS API timed out after 30 s.\n"
                f"  URL   : {_BASE_URL}\n"
                f"  Cause : {exc}\n"
                f"  Check : NTRS service status at https://ntrs.nasa.gov"
            )

    assert resp.status_code in (200, 403), (
        f"Unexpected HTTP status {resp.status_code} from NASA NTRS.\n"
        f"  Expected 200 (open access) or 403 (network block).\n"
        f"  URL      : {resp.url}\n"
        f"  Response : {resp.text[:400]}"
    )


@pytest.mark.asyncio
async def test_ntrs_response_is_json_when_accessible() -> None:
    """When NTRS returns 200, the response body is valid JSON."""
    params = {"q": _QUERY, "rows": 1}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(_BASE_URL, params=params)

    if resp.status_code == 403:
        pytest.skip(
            "NASA NTRS returned 403 on this network — IP/geographic block.\n"
            "Run this test from a different network or VPN to verify JSON parsing."
        )

    try:
        data = resp.json()
    except Exception as exc:
        pytest.fail(
            f"NASA NTRS returned HTTP 200 but response is not valid JSON.\n"
            f"  Content-Type : {resp.headers.get('content-type')}\n"
            f"  Body (first 400): {resp.text[:400]}\n"
            f"  Parse error  : {exc}"
        )

    assert "results" in data, (
        f"NASA NTRS JSON response missing 'results' key.\n"
        f"  Keys present: {list(data.keys())}\n"
        f"  This may indicate an API schema change — update _normalise() in nasa_ntrs.py."
    )


@pytest.mark.asyncio
async def test_ntrs_search_returns_records_when_accessible(config) -> None:
    """search() returns a non-empty list of PaperRecord objects when NTRS is open."""
    from sourcing_agent.databases.nasa_ntrs import search
    from sourcing_agent.models import PaperRecord

    # Check accessibility first
    async with httpx.AsyncClient(timeout=10.0) as client:
        probe = await client.get(_BASE_URL, params={"q": _QUERY, "rows": 1})

    if probe.status_code == 403:
        pytest.skip(
            "NASA NTRS is blocked on this network (403). "
            "Run on a different network to test search()."
        )

    records = await search(_QUERY, config)

    assert len(records) > 0, (
        f"NASA NTRS search() returned 0 records for '{_QUERY}'.\n"
        f"  The API returned 200 so this is not a block issue.\n"
        f"  Check: pagination logic and _normalise() in nasa_ntrs.py.\n"
        f"  Debug: run the probe URL manually:\n"
        f"    curl '{_BASE_URL}?q={_QUERY}&rows=5'"
    )
    assert all(isinstance(r, PaperRecord) for r in records), (
        f"Not all items from NTRS are PaperRecord instances.\n"
        f"  Types: { {type(r).__name__ for r in records} }"
    )


@pytest.mark.asyncio
async def test_ntrs_records_tagged_as_technical_reports_when_accessible(config) -> None:
    """NTRS records should have source_type='technical_report' and source_database set."""
    from sourcing_agent.databases.nasa_ntrs import search

    async with httpx.AsyncClient(timeout=10.0) as client:
        probe = await client.get(_BASE_URL, params={"q": _QUERY, "rows": 1})

    if probe.status_code == 403:
        pytest.skip("NASA NTRS blocked on this network")

    records = await search(_QUERY, config)
    if not records:
        pytest.skip("No records returned from NTRS")

    wrong_db = [
        r for r in records if r.source_database != "NASA Technical Reports Server"
    ]
    assert not wrong_db, (
        f"{len(wrong_db)} record(s) have incorrect source_database.\n"
        f"  Expected : 'NASA Technical Reports Server'\n"
        f"  Found    : { {r.source_database for r in wrong_db} }"
    )

    wrong_type = [r for r in records if r.source_type != "technical_report"]
    assert not wrong_type, (
        f"{len(wrong_type)} record(s) have source_type != 'technical_report'.\n"
        f"  Found: { {r.source_type for r in wrong_type} }\n"
        f"  This is critical — NTRS records must not have section_fit capped at 6.0."
    )


@pytest.mark.asyncio
async def test_ntrs_fast_fail_on_403(config) -> None:
    """After a 403, the fast-fail flag prevents subsequent network calls.

    This test verifies the _ntrs_unavailable module flag works correctly.
    It monkeypatches the HTTP fetch to always return 403 and confirms that
    a second call returns [] without hitting the network again.
    """
    import sourcing_agent.databases.nasa_ntrs as ntrs_mod

    # Reset state from any previous test run
    ntrs_mod._ntrs_unavailable = False

    call_count = 0
    original_fetch = ntrs_mod._fetch

    async def fake_fetch(client, params):  # type: ignore[override]
        nonlocal call_count
        call_count += 1
        ntrs_mod._ntrs_unavailable = True
        return None  # simulates 403 path

    ntrs_mod._fetch = fake_fetch  # type: ignore[assignment]
    try:
        result1 = await ntrs_mod.search("query one", config)
        result2 = await ntrs_mod.search("query two", config)
    finally:
        ntrs_mod._fetch = original_fetch  # type: ignore[assignment]
        ntrs_mod._ntrs_unavailable = False

    assert result1 == [], f"First search() should return [] on 403, got {result1}"
    assert result2 == [], f"Second search() should fast-fail with [], got {result2}"
    assert call_count == 1, (
        f"_fetch() was called {call_count} times, but should only be called ONCE.\n"
        f"  After the first 403, _ntrs_unavailable should prevent subsequent calls.\n"
        f"  Fix: check the 'if _ntrs_unavailable: return []' guard at the top of search()."
    )
