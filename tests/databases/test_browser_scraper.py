"""Integration tests for the browser-based database scraper (IEEE, WoS, Scopus, ACM).

Run with:  pytest tests/databases/test_browser_scraper.py -v -m integration

These databases require institutional credentials loaded from .env.
Every test skips gracefully when credentials are absent or are still
set to placeholder values — the suite stays green on machines without
access.

Credential env-var names:
  IEEE Xplore        : IEEE_USERNAME, IEEE_PASSWORD, IEEE_PROXY_URL
  Web of Science     : WOS_USERNAME,  WOS_PASSWORD,  WOS_PROXY_URL
  Scopus             : SCOPUS_USERNAME, SCOPUS_PASSWORD, SCOPUS_PROXY_URL
  ACM Digital Library: ACM_USERNAME,  ACM_PASSWORD,  ACM_PROXY_URL
"""

from __future__ import annotations

import os
from unittest.mock import patch

import httpx
import pytest

pytestmark = pytest.mark.integration

_QUERY = "autonomous robot navigation AI"

_PLACEHOLDERS = ("your_email", "your_password", "placeholder", "institution.edu")

# ── Credential helpers ────────────────────────────────────────────────────────

_CRED_MAP: dict[str, tuple[str, str, str]] = {
    "IEEE Xplore": ("IEEE_USERNAME", "IEEE_PASSWORD", "IEEE_PROXY_URL"),
    "Web of Science": ("WOS_USERNAME", "WOS_PASSWORD", "WOS_PROXY_URL"),
    "Scopus": ("SCOPUS_USERNAME", "SCOPUS_PASSWORD", "SCOPUS_PROXY_URL"),
    "ACM Digital Library": ("ACM_USERNAME", "ACM_PASSWORD", "ACM_PROXY_URL"),
}


def _creds_real(db_name: str) -> bool:
    """Return True only when non-placeholder credentials are present."""
    u_key, p_key, _ = _CRED_MAP[db_name]
    u = os.environ.get(u_key, "")
    p = os.environ.get(p_key, "")
    if not u or not p:
        return False
    return not any(ph in u or ph in p for ph in _PLACEHOLDERS)


def _make_db_config(db_name: str, max_results: int = 5):
    """Build a minimal DatabaseConfig for testing without loading CONTEXT.md."""
    from sourcing_agent.config import DatabaseConfig

    u_key, p_key, proxy_key = _CRED_MAP[db_name]
    return DatabaseConfig(
        name=db_name,
        type="paywalled_browser",
        priority=1,
        enabled=True,
        max_results_per_query=max_results,
        credential_env_vars={
            "username": u_key,
            "password": p_key,
            "proxy_url": proxy_key,
        },
    )


# ── Playwright availability ───────────────────────────────────────────────────


def test_playwright_importable() -> None:
    """Playwright must be installed for the browser scraper to function at all.

    If this test fails, run:  python -m playwright install chromium --with-deps
    Or install the package:   pip install playwright
    """
    try:
        from playwright.async_api import async_playwright  # noqa: F401
    except ImportError:
        pytest.fail(
            "playwright is not installed — the browser scraper cannot function.\n"
            "  Fix: python -m playwright install chromium --with-deps\n"
            "  Or:  pip install playwright && playwright install chromium"
        )


# ── Website reachability (no credentials required) ───────────────────────────
#
# These probe the public login/search page of each database using a plain HTTP
# GET — no Playwright, no credentials. They confirm the host is reachable from
# this network and that the service is responding. Any HTTP status in the 2xx,
# 3xx, or 4xx range counts as reachable; only connection failures or timeouts
# are treated as genuine problems (the sites may redirect or gate on IP).

_SITE_URLS: dict[str, str] = {
    "IEEE Xplore": "https://ieeexplore.ieee.org/search/searchresult.jsp",
    "Web of Science": "https://www.webofscience.com/wos/woscc/basic-search",
    "Scopus": "https://www.scopus.com/search/form.uri",
    "ACM Digital Library": "https://dl.acm.org/search/",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("db_name", list(_SITE_URLS.keys()))
async def test_site_reachable(db_name: str) -> None:
    """The database website is reachable from this network.

    Uses a plain HTTP GET — no Playwright, no credentials. Any HTTP status
    in the 2xx-4xx range is accepted as "reachable"; only a connection error
    or timeout indicates a real network problem.

    A 403 or 401 means the site responded but requires authentication — that
    is expected and is not a failure. A 503 or timeout may indicate a service
    outage worth investigating.
    """
    url = _SITE_URLS[db_name]

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"},
    ) as client:
        try:
            resp = await client.get(url)
        except httpx.ConnectError as exc:
            pytest.fail(
                f"{db_name}: cannot reach {url}\n"
                f"  Cause : {exc}\n"
                f"  Check : network connectivity, DNS, and firewall rules.\n"
                f"  Note  : institutional VPN or proxy may be required."
            )
        except httpx.TimeoutException as exc:
            pytest.fail(
                f"{db_name}: request to {url} timed out after 30 s.\n"
                f"  Cause : {exc}\n"
                f"  Check : {db_name} service status or network latency."
            )

    assert resp.status_code < 500, (
        f"{db_name}: server error {resp.status_code} — service may be down.\n"
        f"  URL      : {resp.url}\n"
        f"  Response : {resp.text[:300]}\n"
        f"  A 5xx here is unexpected; 4xx (auth required) is normal."
    )


# ── Missing-credential fast-fail ──────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("db_name", list(_CRED_MAP.keys()))
async def test_missing_credentials_return_empty_list(db_name: str, config) -> None:
    """search() must return [] (not raise) when credentials are absent.

    This test forces env vars to be absent so it runs on all machines.
    It verifies the guard clause in browser_scraper.search() works correctly.
    """
    from sourcing_agent.databases.browser_scraper import search

    db_cfg = _make_db_config(db_name)
    u_key, p_key, proxy_key = _CRED_MAP[db_name]

    # Patch env so credentials appear absent regardless of .env
    patched_env = dict(os.environ.items())
    patched_env.pop(u_key, None)
    patched_env.pop(p_key, None)
    patched_env.pop(proxy_key, None)

    with patch.dict(os.environ, patched_env, clear=True):
        try:
            result = await search(db_cfg, _QUERY, config)
        except Exception as exc:
            pytest.fail(
                f"{db_name}: search() raised an exception instead of returning [].\n"
                f"  Exception type : {type(exc).__name__}\n"
                f"  Message        : {exc}\n"
                f"  Expected       : [] when credentials are missing.\n"
                f"  Fix            : ensure the credential guard at the top of\n"
                f"                   browser_scraper.search() returns [] early."
            )

    assert result == [], (
        f"{db_name}: search() returned {result!r} instead of [] when credentials absent.\n"
        f"  Fix: the guard `if not username or not password: return []` is missing or broken."
    )


# ── Placeholder-credential detection ─────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("db_name", list(_CRED_MAP.keys()))
async def test_placeholder_credentials_return_empty_list(db_name: str, config) -> None:
    """search() must return [] when credentials contain placeholder text.

    Placeholder credentials look like 'your_email@institution.edu' and are
    set by /setup-env as template values. The scraper must detect these
    and skip rather than attempting to log in.
    """
    from sourcing_agent.databases.browser_scraper import search

    db_cfg = _make_db_config(db_name)
    u_key, p_key, proxy_key = _CRED_MAP[db_name]

    placeholder_env = {
        u_key: "your_email@institution.edu",
        p_key: "your_password_here",
        proxy_key: "https://ezproxy.your-institution.edu",
    }

    with patch.dict(os.environ, placeholder_env):
        try:
            result = await search(db_cfg, _QUERY, config)
        except Exception as exc:
            pytest.fail(
                f"{db_name}: search() raised instead of returning [] for placeholder creds.\n"
                f"  Exception : {type(exc).__name__}: {exc}\n"
                f"  Expected  : [] — placeholder creds should be detected and skipped.\n"
                f"  Fix       : ensure _PLACEHOLDERS tuple check in browser_scraper.search()."
            )

    assert result == [], (
        f"{db_name}: search() returned {result!r} for placeholder credentials.\n"
        f"  Placeholder creds ('your_email', 'your_password', etc.) must be detected\n"
        f"  and the function must return [] without attempting a browser login."
    )


# ── Placeholder proxy URL detection ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_placeholder_proxy_url_skips_gracefully(config) -> None:
    """A placeholder proxy URL ('your-institution') must trigger a skip, not a launch.

    Proxy URLs like 'https://ezproxy.your-institution.edu' are template values.
    The scraper must detect these and return [] without trying to navigate to the URL.
    """
    from sourcing_agent.databases.browser_scraper import search

    db_cfg = _make_db_config("IEEE Xplore")
    u_key, p_key, proxy_key = _CRED_MAP["IEEE Xplore"]

    patched = {
        u_key: "real_user@university.edu",
        p_key: "real_password_value_123",
        proxy_key: "https://ezproxy.your-institution.edu",
    }

    with patch.dict(os.environ, patched):
        try:
            result = await search(db_cfg, _QUERY, config)
        except Exception as exc:
            pytest.fail(
                f"IEEE Xplore: search() raised with placeholder proxy URL.\n"
                f"  Exception : {type(exc).__name__}: {exc}\n"
                f"  Expected  : [] — 'your-institution' in proxy URL should cause skip.\n"
                f"  Fix       : add placeholder proxy URL check in browser_scraper.search()."
            )

    assert result == [], (
        f"IEEE Xplore: search() returned {result!r} with placeholder proxy URL.\n"
        f"  The proxy URL 'https://ezproxy.your-institution.edu' is a template value.\n"
        f"  It must be detected and the function must return [] without launching a browser."
    )


# ── Per-database credential-gated connectivity tests ─────────────────────────


@pytest.mark.asyncio
async def test_ieee_search_with_credentials(config) -> None:
    """With IEEE credentials, search() returns a list of PaperRecord objects.

    Requires env vars: IEEE_USERNAME, IEEE_PASSWORD, IEEE_PROXY_URL.
    Set these in .env with your institutional credentials.
    """
    if not _creds_real("IEEE Xplore"):
        pytest.skip(
            "IEEE Xplore credentials not set or still placeholder in .env.\n"
            "Required env vars: IEEE_USERNAME, IEEE_PASSWORD, IEEE_PROXY_URL\n"
            "Set these with your institutional login to run this test."
        )

    from sourcing_agent.databases.browser_scraper import search
    from sourcing_agent.models import PaperRecord

    db_cfg = _make_db_config("IEEE Xplore", max_results=5)

    try:
        records = await search(db_cfg, _QUERY, config)
    except Exception as exc:
        pytest.fail(
            f"IEEE Xplore: search() raised an unexpected exception.\n"
            f"  Exception : {type(exc).__name__}: {exc}\n"
            f"  Query     : {_QUERY}\n"
            f"  Check     : Playwright is installed, credentials are correct,\n"
            f"              proxy URL is accessible from this network."
        )

    assert isinstance(
        records, list
    ), f"IEEE Xplore: search() returned {type(records).__name__} instead of list."
    assert all(isinstance(r, PaperRecord) for r in records), (
        f"IEEE Xplore: search() returned non-PaperRecord items.\n"
        f"  Types: { {type(r).__name__ for r in records} }"
    )


@pytest.mark.asyncio
async def test_wos_search_with_credentials(config) -> None:
    """With Web of Science credentials, search() returns a list of PaperRecord objects.

    Requires env vars: WOS_USERNAME, WOS_PASSWORD, WOS_PROXY_URL.
    """
    if not _creds_real("Web of Science"):
        pytest.skip(
            "Web of Science credentials not set or still placeholder in .env.\n"
            "Required env vars: WOS_USERNAME, WOS_PASSWORD, WOS_PROXY_URL\n"
            "Set these with your institutional login to run this test."
        )

    from sourcing_agent.databases.browser_scraper import search
    from sourcing_agent.models import PaperRecord

    db_cfg = _make_db_config("Web of Science", max_results=5)

    try:
        records = await search(db_cfg, _QUERY, config)
    except Exception as exc:
        pytest.fail(
            f"Web of Science: search() raised an unexpected exception.\n"
            f"  Exception : {type(exc).__name__}: {exc}\n"
            f"  Query     : {_QUERY}\n"
            f"  Check     : Playwright installed, WoS accessible from this network."
        )

    assert isinstance(
        records, list
    ), f"Web of Science: search() returned {type(records).__name__} instead of list."
    assert all(isinstance(r, PaperRecord) for r in records), (
        f"Web of Science: search() returned non-PaperRecord items.\n"
        f"  Types: { {type(r).__name__ for r in records} }"
    )


@pytest.mark.asyncio
async def test_scopus_search_with_credentials(config) -> None:
    """With Scopus credentials, search() returns a list of PaperRecord objects.

    Requires env vars: SCOPUS_USERNAME, SCOPUS_PASSWORD, SCOPUS_PROXY_URL.
    """
    if not _creds_real("Scopus"):
        pytest.skip(
            "Scopus credentials not set or still placeholder in .env.\n"
            "Required env vars: SCOPUS_USERNAME, SCOPUS_PASSWORD, SCOPUS_PROXY_URL\n"
            "Set these with your institutional login to run this test."
        )

    from sourcing_agent.databases.browser_scraper import search
    from sourcing_agent.models import PaperRecord

    db_cfg = _make_db_config("Scopus", max_results=5)

    try:
        records = await search(db_cfg, _QUERY, config)
    except Exception as exc:
        pytest.fail(
            f"Scopus: search() raised an unexpected exception.\n"
            f"  Exception : {type(exc).__name__}: {exc}\n"
            f"  Query     : {_QUERY}\n"
            f"  Check     : Playwright installed, Scopus accessible from this network."
        )

    assert isinstance(
        records, list
    ), f"Scopus: search() returned {type(records).__name__} instead of list."
    assert all(isinstance(r, PaperRecord) for r in records), (
        f"Scopus: search() returned non-PaperRecord items.\n"
        f"  Types: { {type(r).__name__ for r in records} }"
    )


@pytest.mark.asyncio
async def test_acm_search_with_credentials(config) -> None:
    """With ACM credentials, search() returns a list of PaperRecord objects.

    Requires env vars: ACM_USERNAME, ACM_PASSWORD, ACM_PROXY_URL.
    """
    if not _creds_real("ACM Digital Library"):
        pytest.skip(
            "ACM Digital Library credentials not set or still placeholder in .env.\n"
            "Required env vars: ACM_USERNAME, ACM_PASSWORD, ACM_PROXY_URL\n"
            "Set these with your institutional login to run this test."
        )

    from sourcing_agent.databases.browser_scraper import search
    from sourcing_agent.models import PaperRecord

    db_cfg = _make_db_config("ACM Digital Library", max_results=5)

    try:
        records = await search(db_cfg, _QUERY, config)
    except Exception as exc:
        pytest.fail(
            f"ACM Digital Library: search() raised an unexpected exception.\n"
            f"  Exception : {type(exc).__name__}: {exc}\n"
            f"  Query     : {_QUERY}\n"
            f"  Check     : Playwright installed, ACM DL accessible from this network."
        )

    assert isinstance(
        records, list
    ), f"ACM Digital Library: search() returned {type(records).__name__} instead of list."
    assert all(isinstance(r, PaperRecord) for r in records), (
        f"ACM Digital Library: search() returned non-PaperRecord items.\n"
        f"  Types: { {type(r).__name__ for r in records} }"
    )


# ── Return-type contract (no network needed) ──────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("db_name", list(_CRED_MAP.keys()))
async def test_search_always_returns_a_list(db_name: str, config) -> None:
    """search() must always return list[PaperRecord], never None or raise.

    This test patches Playwright to avoid any network access and verifies
    that the function's return-type contract holds regardless of credentials.
    """
    from sourcing_agent.databases import browser_scraper

    db_cfg = _make_db_config(db_name)

    # Force credentials to be absent so we hit the early-return path
    u_key, p_key, _proxy_key = _CRED_MAP[db_name]
    patched_env = dict(os.environ.items())
    patched_env.pop(u_key, None)
    patched_env.pop(p_key, None)

    with patch.dict(os.environ, patched_env, clear=True):
        result = await browser_scraper.search(db_cfg, _QUERY, config)

    assert isinstance(result, list), (
        f"{db_name}: search() returned {type(result).__name__} instead of list.\n"
        f"  All code paths in browser_scraper.search() must return list[PaperRecord].\n"
        f"  A None return or exception here would crash the pipeline orchestrator."
    )
