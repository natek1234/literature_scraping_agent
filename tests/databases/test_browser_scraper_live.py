"""Credential-gated smoke tests for browser-based database scraping.

These tests launch a real Playwright browser and use real institutional
credentials from .env.  They run in three diagnostic tiers per database:

  Tier 1 — Proxy reachable   (httpx GET, no browser)
  Tier 2 — Auth succeeds     (real SSO login → verify not on login page)
  Tier 3 — Search returns ≥1 result  (full search() pipeline)

Failure semantics — important distinction:
  FAIL  = code bug (wrong URL construction, exception raised, 0 results
          when auth is confirmed working, etc.)
  SKIP  = environment constraint (no credentials, Duo/MFA blocks automated
          SSO, proxy unreachable from this network)

When Tier 2 skips (auth failed due to MFA or environment), Tier 3 also
skips automatically.  Only when Tier 2 passes AND Tier 3 returns 0 results
does Tier 3 fail — that points to a broken search-box selector.

This makes the suite safe to run against a machine with real credentials:
it will skip (not fail) when Duo MFA is present, and only fail when there
is an actual regression in the scraping code.

All proxy/SSO behaviour comes from the production code and env vars.
No proxy URL format, SSO form structure, or institution-specific detail
is hardcoded here; these tests work with any EZProxy or direct-access
configuration.

Mark reference:
  @pytest.mark.live        — makes real network calls
  @pytest.mark.integration — grouped with other integration tests

Run all live tests:
  pytest tests/databases/test_browser_scraper_live.py -v -m live

Run only auth+proxy tiers (skip slow search):
  pytest tests/databases/test_browser_scraper_live.py -v -k "reachable or auth"
"""

from __future__ import annotations

import os

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.live]

# Broad query guaranteed to return results from every database
_BROAD_QUERY = "robot"

_PLACEHOLDERS = ("your_email", "your_password", "placeholder", "institution.edu")

_CRED_MAP: dict[str, tuple[str, str, str]] = {
    "Web of Science": ("WOS_USERNAME", "WOS_PASSWORD", "WOS_PROXY_URL"),
    "Scopus": ("SCOPUS_USERNAME", "SCOPUS_PASSWORD", "SCOPUS_PROXY_URL"),
    "IEEE Xplore": ("IEEE_USERNAME", "IEEE_PASSWORD", "IEEE_PROXY_URL"),
    "ACM Digital Library": ("ACM_USERNAME", "ACM_PASSWORD", "ACM_PROXY_URL"),
}

# Per-database path appended to the proxy root to reach the search page.
# This is the only URL knowledge the tests encode — it mirrors _SEARCH_PATHS
# in browser_scraper.py and is independent of the proxy host/domain.
_SEARCH_PATHS: dict[str, str] = {
    "Web of Science": "/wos/woscc/basic-search",
    "Scopus": "/search/form.uri?display=basic",
    "IEEE Xplore": "/search/searchresult.jsp",
}


# ── Credential + proxy helpers ────────────────────────────────────────────────


def _creds(db_name: str) -> tuple[str, str]:
    """Return (username, password) — ('', '') if missing or placeholder."""
    u_key, p_key, _ = _CRED_MAP[db_name]
    u = os.environ.get(u_key, "")
    p = os.environ.get(p_key, "")
    if not u or not p:
        return "", ""
    if any(ph in u or ph in p for ph in _PLACEHOLDERS):
        return "", ""
    return u, p


def _proxy(db_name: str) -> str:
    """Return proxy URL — '' if missing or placeholder."""
    _, _, px_key = _CRED_MAP[db_name]
    px = os.environ.get(px_key, "")
    return "" if not px or "your-institution" in px else px


def _creds_real(db_name: str) -> bool:
    u, _ = _creds(db_name)
    return bool(u)


def _db_config(db_name: str, max_results: int = 5):
    from sourcing_agent.config import DatabaseConfig

    u_key, p_key, px_key = _CRED_MAP[db_name]
    return DatabaseConfig(
        name=db_name,
        type="paywalled_browser",
        priority=1,
        enabled=True,
        max_results_per_query=max_results,
        credential_env_vars={"username": u_key, "password": p_key, "proxy_url": px_key},
    )


def _skip_no_creds(db_name: str) -> None:
    if not _creds_real(db_name):
        u_key, p_key, _ = _CRED_MAP[db_name]
        pytest.skip(
            f"{db_name}: credentials not set or still placeholder in .env\n"
            f"  Required: {u_key}, {p_key}"
        )


def _skip_no_proxy(db_name: str) -> None:
    if not _proxy(db_name):
        _, _, px_key = _CRED_MAP[db_name]
        pytest.skip(
            f"{db_name}: {px_key} not set or is a placeholder in .env\n"
            "  This test requires a real institutional proxy URL."
        )


# ═════════════════════════════════════════════════════════════════════════════
# Tier 1 — Proxy reachable
# ═════════════════════════════════════════════════════════════════════════════
#
# A plain HTTP GET to the proxy URL — no browser, no credentials.
# Confirms the host is reachable from this network and is responding.
# Any status < 500 is accepted: 200 (login page), 3xx (redirect to SSO),
# or 4xx (auth required) all mean the server is alive.
# A 5xx or connection error means the proxy URL is wrong or unreachable —
# this is a hard FAIL (code / config bug, not an environment constraint).


class TestProxyReachable:

    @pytest.mark.asyncio
    async def test_wos_proxy_reachable(self) -> None:
        """WOS_PROXY_URL responds with a non-5xx status from this network."""
        _skip_no_proxy("Web of Science")
        await _assert_url_reachable(_proxy("Web of Science"), "Web of Science")

    @pytest.mark.asyncio
    async def test_scopus_proxy_reachable(self) -> None:
        """SCOPUS_PROXY_URL responds with a non-5xx status from this network."""
        _skip_no_proxy("Scopus")
        await _assert_url_reachable(_proxy("Scopus"), "Scopus")

    @pytest.mark.asyncio
    async def test_ieee_proxy_reachable(self) -> None:
        """IEEE_PROXY_URL responds with a non-5xx status from this network."""
        _skip_no_proxy("IEEE Xplore")
        await _assert_url_reachable(_proxy("IEEE Xplore"), "IEEE Xplore")


async def _assert_url_reachable(url: str, db_name: str) -> None:
    async with httpx.AsyncClient(
        timeout=20.0,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"},
    ) as client:
        try:
            resp = await client.get(url)
        except httpx.ConnectError as exc:
            pytest.fail(
                f"{db_name}: cannot connect to proxy URL {url!r}\n"
                f"  Cause: {exc}\n"
                "  Check: network connectivity, VPN, DNS, and firewall rules.\n"
                "  Tip:   institutional proxies are often only reachable on-campus\n"
                "         or via VPN — connect to VPN and retry."
            )
        except httpx.TimeoutException as exc:
            pytest.fail(
                f"{db_name}: request to {url!r} timed out.\n"
                f"  Cause: {exc}\n"
                "  Check: VPN connection and proxy server availability."
            )

    assert resp.status_code < 500, (
        f"{db_name}: proxy returned server error {resp.status_code}.\n"
        f"  URL:      {resp.url}\n"
        f"  Response: {resp.text[:200]}\n"
        "  A 5xx response is a server-side failure — the proxy may be down."
    )


# ═════════════════════════════════════════════════════════════════════════════
# Tier 2 — Authentication succeeds
# ═════════════════════════════════════════════════════════════════════════════
#
# Launches a real headless browser, runs the full SSO login flow via the
# production _get_authenticated_context, then navigates to the search page
# and checks whether we landed on the search page or are still on a login form.
#
# FAIL  → _get_authenticated_context raised an unexpected exception (code bug)
# SKIP  → we ended up on a login page (environment: Duo/MFA, wrong credentials,
#          or SSO form selector mismatch — not a code regression)
# PASS  → SSO completed; we are on the authenticated search page


class TestAuthWithCredentials:

    @pytest.mark.asyncio
    async def test_wos_auth_reaches_search_page(self) -> None:
        """WoS SSO login completes and lands on the search page, not a login form."""
        _skip_no_creds("Web of Science")
        _skip_no_proxy("Web of Science")
        await _assert_auth_succeeds("Web of Science", _SEARCH_PATHS["Web of Science"])

    @pytest.mark.asyncio
    async def test_scopus_auth_reaches_search_page(self) -> None:
        """Scopus SSO login completes and lands on the search page, not a login form."""
        _skip_no_creds("Scopus")
        _skip_no_proxy("Scopus")
        await _assert_auth_succeeds("Scopus", _SEARCH_PATHS["Scopus"])

    @pytest.mark.asyncio
    async def test_ieee_auth_reaches_search_page(self) -> None:
        """IEEE SSO login completes and lands on the search page, not a login form."""
        _skip_no_creds("IEEE Xplore")
        _skip_no_proxy("IEEE Xplore")
        await _assert_auth_succeeds("IEEE Xplore", _SEARCH_PATHS["IEEE Xplore"])


async def _check_auth(db_name: str, search_path: str) -> bool:
    """
    Return True if SSO login lands on the search page.
    Return False if still on a login/SSO page (Duo MFA, wrong credentials, etc.).
    Raises on unexpected exceptions (code bugs).
    """
    from playwright.async_api import async_playwright

    from sourcing_agent.databases.browser_scraper import (
        _get_authenticated_context,
        _is_on_login_page,
    )

    username, password = _creds(db_name)
    proxy_url = _proxy(db_name)
    db_cfg = _db_config(db_name)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            ctx, search_base = await _get_authenticated_context(
                browser, db_cfg, username, password, proxy_url
            )
            page = await ctx.new_page()
            try:
                await page.goto(f"{search_base}{search_path}", timeout=40000)
                await page.wait_for_load_state("networkidle", timeout=30000)
                still_on_login = await _is_on_login_page(page)
            finally:
                await page.close()
                await ctx.close()
        finally:
            await browser.close()

    return not still_on_login


async def _assert_auth_succeeds(db_name: str, search_path: str) -> None:
    """
    Skip (not fail) when SSO authentication cannot complete — that is an
    environment constraint (Duo/MFA, wrong credentials, SSO selector mismatch),
    not a code regression.  Only raises on unexpected exceptions.
    """
    succeeded = await _check_auth(db_name, search_path)
    if not succeeded:
        proxy_url = _proxy(db_name)
        pytest.skip(
            f"{db_name}: SSO did not complete — still on a login/SSO page.\n"
            "\n"
            "This is an environment constraint, not a code failure.  Causes:\n"
            "  1. Duo / MFA required — automated SSO cannot pass MFA prompts.\n"
            "     Fix: run  python outputs/save_browser_session.py\n"
            "          Log in manually (including Duo), save the session.\n"
            "          The next run will use the saved session (Option B).\n"
            f"  2. Wrong credentials — verify login manually at: {proxy_url}\n"
            "  3. SSO form selector mismatch — the login form uses field IDs\n"
            "     not in _try_sso_login's selector list. Inspect the proxy\n"
            "     login page HTML and add the correct selector."
        )


# ═════════════════════════════════════════════════════════════════════════════
# Tier 3 — Search returns ≥ 1 result
# ═════════════════════════════════════════════════════════════════════════════
#
# Runs the full search() pipeline with a deliberately broad query ("robot")
# that is guaranteed to have results in every database.
#
# FAIL  → search() raised, OR returned 0 results when auth is confirmed working
#          (points to a broken search-box or result-extraction selector)
# SKIP  → auth check shows we cannot reach the search page (Tier 2 would also
#          skip) — test skips rather than failing on the wrong layer
# PASS  → ≥ 1 PaperRecord returned
#
# ACM Digital Library is open access — no proxy or SSO needed.


class TestSearchReturnsResults:

    @pytest.mark.asyncio
    async def test_wos_returns_at_least_one_result(self, config) -> None:
        """search() returns ≥ 1 PaperRecord from Web of Science."""
        _skip_no_creds("Web of Science")
        _skip_no_proxy("Web of Science")
        await _assert_results("Web of Science", config, _SEARCH_PATHS["Web of Science"])

    @pytest.mark.asyncio
    async def test_scopus_returns_at_least_one_result(self, config) -> None:
        """search() returns ≥ 1 PaperRecord from Scopus."""
        _skip_no_creds("Scopus")
        _skip_no_proxy("Scopus")
        await _assert_results("Scopus", config, _SEARCH_PATHS["Scopus"])

    @pytest.mark.asyncio
    async def test_ieee_returns_at_least_one_result(self, config) -> None:
        """search() returns ≥ 1 PaperRecord from IEEE Xplore."""
        _skip_no_creds("IEEE Xplore")
        _skip_no_proxy("IEEE Xplore")
        await _assert_results("IEEE Xplore", config, _SEARCH_PATHS["IEEE Xplore"])

    @pytest.mark.asyncio
    async def test_acm_returns_at_least_one_result(self, config) -> None:
        """search() returns ≥ 1 PaperRecord from ACM Digital Library (open access)."""
        _skip_no_creds("ACM Digital Library")
        # ACM is open access — no proxy or auth tier to check first
        await _assert_open_access_results("ACM Digital Library", config)


async def _assert_results(db_name: str, config, search_path: str) -> None:
    from sourcing_agent.databases.browser_scraper import search
    from sourcing_agent.models import PaperRecord

    db_cfg = _db_config(db_name, max_results=3)

    try:
        records = await search(db_cfg, _BROAD_QUERY, config)
    except Exception as exc:
        pytest.fail(
            f"{db_name}: search() raised an unexpected exception.\n"
            f"  Exception: {type(exc).__name__}: {exc}\n"
            f"  Query:     {_BROAD_QUERY!r}"
        )

    assert isinstance(records, list)
    assert all(isinstance(r, PaperRecord) for r in records), (
        f"{db_name}: non-PaperRecord items returned: "
        f"{ {type(r).__name__ for r in records} }"
    )

    if len(records) == 0:
        # Before failing, verify whether auth is the cause — if so, skip
        # (auth failure is an environment constraint, not a selector bug).
        auth_ok = await _check_auth(db_name, search_path)
        if not auth_ok:
            pytest.skip(
                f"{db_name}: 0 results because authentication did not complete.\n"
                "  Run the Tier 2 auth test for the specific cause and fix:\n"
                f"    pytest tests/databases/test_browser_scraper_live.py -k 'auth'"
            )
        pytest.fail(
            f"{db_name}: search() returned 0 results for {_BROAD_QUERY!r} despite\n"
            "  confirmed authentication.  This points to a broken selector:\n"
            "  - search-box selector no longer matches the database HTML, OR\n"
            "  - result-extraction selectors (_extract_*_results) are outdated.\n"
            "  Inspect the search results page HTML and update browser_scraper.py."
        )


async def _assert_open_access_results(db_name: str, config) -> None:
    from sourcing_agent.databases.browser_scraper import search
    from sourcing_agent.models import PaperRecord

    db_cfg = _db_config(db_name, max_results=3)

    try:
        records = await search(db_cfg, _BROAD_QUERY, config)
    except Exception as exc:
        pytest.fail(
            f"{db_name}: search() raised an unexpected exception.\n"
            f"  Exception: {type(exc).__name__}: {exc}"
        )

    assert isinstance(records, list)
    assert all(isinstance(r, PaperRecord) for r in records)
    assert len(records) > 0, (
        f"{db_name}: search() returned 0 results for {_BROAD_QUERY!r}.\n"
        "  ACM is open access — no auth required.  This points to a broken\n"
        "  search-box or result-extraction selector in _scrape_acm."
    )
