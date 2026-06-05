"""Unit tests for browser_scraper authentication and navigation logic.

No browser, no network, no credentials required.  All Playwright calls are
mocked via AsyncMock + a sys.modules patch that makes isinstance(mock, Page)
pass by substituting the real Playwright types with ``object``.

Tests are organised around the specific failure modes identified in the prior
sourcing run:

  1. _session_path            — correct slug → file path per database
  2. _is_on_login_page        — detects SSO forms; clears authenticated pages
  3. _try_sso_login           — Shibboleth selectors (j_username/j_password)
                                before generic fallbacks
  4. _save_session            — calls context.storage_state with the right path
  5. Scraper URL construction — _scrape_wos / _scrape_scopus / _scrape_ieee
                                navigate via proxy-relative base, never the
                                hardcoded direct vendor URL
  6. _get_authenticated_context
       Option B (saved session)  → loads storage_state; no SSO call made
       Option B expiry           → detects login page; falls back to Option A
       No session file           → skips Option B; goes straight to Option A
       search_base               → always the proxy root when proxy_url set
"""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Playwright type stub ──────────────────────────────────────────────────────
# Each scraper function does:
#   from playwright.async_api import Page
#   assert isinstance(page, Page)
# By making Page = object we satisfy the isinstance check for plain AsyncMocks.

_PW_STUB = types.ModuleType("playwright.async_api")
_PW_STUB.Page = object
_PW_STUB.Browser = object
_PW_STUB.BrowserContext = object


@pytest.fixture(autouse=True)
def _inject_playwright_types():
    with patch.dict(sys.modules, {"playwright.async_api": _PW_STUB}):
        yield


@pytest.fixture(autouse=True)
def _no_sleep():
    """Suppress asyncio.sleep so auth tests don't wait 3 seconds each."""
    with patch("asyncio.sleep", new=AsyncMock()):
        yield


# ── Shared proxy URLs ─────────────────────────────────────────────────────────

_WOS_PROXY = "https://www-webofscience-com.ezproxy4.library.arizona.edu"
_SCOPUS_PROXY = "https://www-scopus-com.ezproxy4.library.arizona.edu"
_IEEE_PROXY = "https://ieeexplore-ieee-org.ezproxy4.library.arizona.edu"


# ── DatabaseConfig factories ──────────────────────────────────────────────────


def _db_config(name: str, max_results: int = 5):
    from sourcing_agent.config import DatabaseConfig

    cred_map = {
        "Web of Science": ("WOS_USERNAME", "WOS_PASSWORD", "WOS_PROXY_URL"),
        "Scopus": ("SCOPUS_USERNAME", "SCOPUS_PASSWORD", "SCOPUS_PROXY_URL"),
        "IEEE Xplore": ("IEEE_USERNAME", "IEEE_PASSWORD", "IEEE_PROXY_URL"),
        "ACM Digital Library": ("ACM_USERNAME", "ACM_PASSWORD", "ACM_PROXY_URL"),
    }
    u, p, px = cred_map[name]
    return DatabaseConfig(
        name=name,
        type="paywalled_browser",
        priority=1,
        enabled=True,
        max_results_per_query=max_results,
        credential_env_vars={"username": u, "password": p, "proxy_url": px},
    )


# ── Page factory ──────────────────────────────────────────────────────────────


def _page(present_selectors: frozenset[str] = frozenset()) -> AsyncMock:
    """Return a mock page where only the listed selectors are found."""
    page = AsyncMock()

    async def qs(sel: str) -> MagicMock | None:
        return MagicMock() if sel in present_selectors else None

    page.query_selector.side_effect = qs
    page.query_selector_all.return_value = []
    return page


# ═════════════════════════════════════════════════════════════════════════════
# 1. _session_path
# ═════════════════════════════════════════════════════════════════════════════


class TestSessionPath:
    def test_web_of_science_slug(self):
        from sourcing_agent.databases.browser_scraper import _session_path

        p = _session_path("Web of Science")
        assert p.name == "web_of_science_session.json"

    def test_scopus_slug(self):
        from sourcing_agent.databases.browser_scraper import _session_path

        p = _session_path("Scopus")
        assert p.name == "scopus_session.json"

    def test_ieee_xplore_slug(self):
        from sourcing_agent.databases.browser_scraper import _session_path

        p = _session_path("IEEE Xplore")
        assert p.name == "ieee_xplore_session.json"

    def test_all_paths_share_session_dir(self):
        from sourcing_agent.databases import browser_scraper

        for name in ("Web of Science", "Scopus", "IEEE Xplore"):
            p = browser_scraper._session_path(name)
            assert p.parent == browser_scraper._SESSION_DIR


# ═════════════════════════════════════════════════════════════════════════════
# 2. _is_on_login_page
# ═════════════════════════════════════════════════════════════════════════════


class TestIsOnLoginPage:
    """Returns True when any login-form selector is present; False otherwise."""

    @pytest.mark.asyncio
    async def test_j_username_returns_true(self):
        from sourcing_agent.databases.browser_scraper import _is_on_login_page

        assert await _is_on_login_page(_page({"#j_username"})) is True

    @pytest.mark.asyncio
    async def test_j_username_name_attr_returns_true(self):
        from sourcing_agent.databases.browser_scraper import _is_on_login_page

        assert await _is_on_login_page(_page({'input[name="j_username"]'})) is True

    @pytest.mark.asyncio
    async def test_netid_returns_true(self):
        from sourcing_agent.databases.browser_scraper import _is_on_login_page

        assert await _is_on_login_page(_page({"#netid"})) is True

    @pytest.mark.asyncio
    async def test_generic_username_returns_true(self):
        from sourcing_agent.databases.browser_scraper import _is_on_login_page

        assert await _is_on_login_page(_page({"#username"})) is True

    @pytest.mark.asyncio
    async def test_no_login_selector_returns_false(self):
        from sourcing_agent.databases.browser_scraper import _is_on_login_page

        # A page with only a search box — authenticated, no login form
        assert (
            await _is_on_login_page(_page({'input[name="search-main-box"]'})) is False
        )

    @pytest.mark.asyncio
    async def test_empty_page_returns_false(self):
        from sourcing_agent.databases.browser_scraper import _is_on_login_page

        assert await _is_on_login_page(_page()) is False


# ═════════════════════════════════════════════════════════════════════════════
# 3. _try_sso_login — selector priority
# ═════════════════════════════════════════════════════════════════════════════


class TestTrySsoLogin:
    """Shibboleth selectors must be tried before generic fallbacks."""

    @pytest.mark.asyncio
    async def test_fills_j_username_when_present(self):
        """When #j_username is in the DOM it must be used, not #username."""
        from sourcing_agent.databases.browser_scraper import _try_sso_login

        page = _page({"#j_username", "#j_password", 'button[type="submit"]'})
        page.fill = AsyncMock()
        page.click = AsyncMock()

        await _try_sso_login(page, "user@arizona.edu", "secret", "Web of Science")

        fill_calls = page.fill.call_args_list
        username_fills = [
            c
            for c in fill_calls
            if "j_username" in str(c) or "username" in str(c).lower()
        ]
        assert username_fills, "fill() should have been called for a username field"
        # The selector used must be the Shibboleth one
        first_selector = fill_calls[0].args[0]
        assert first_selector in ("#j_username", 'input[name="j_username"]'), (
            f"Expected Shibboleth selector, got {first_selector!r}. "
            "Shibboleth selectors (j_username) must precede generic ones (#username)."
        )

    @pytest.mark.asyncio
    async def test_falls_back_to_generic_username_when_j_username_absent(self):
        """When no j_username selector is found, #username must be used."""
        from sourcing_agent.databases.browser_scraper import _try_sso_login

        page = _page({"#username", "#password", 'button[type="submit"]'})
        page.fill = AsyncMock()
        page.click = AsyncMock()

        await _try_sso_login(page, "user@arizona.edu", "secret", "Scopus")

        fill_selectors = [c.args[0] for c in page.fill.call_args_list]
        assert "#username" in fill_selectors, (
            "Expected #username as fallback when j_username is absent. "
            f"Got: {fill_selectors}"
        )

    @pytest.mark.asyncio
    async def test_fills_j_password_when_present(self):
        """Shibboleth j_password must be used over #password."""
        from sourcing_agent.databases.browser_scraper import _try_sso_login

        page = _page({"#j_username", "#j_password", 'button[type="submit"]'})
        page.fill = AsyncMock()
        page.click = AsyncMock()

        await _try_sso_login(page, "user@arizona.edu", "secret", "Web of Science")

        fill_selectors = [c.args[0] for c in page.fill.call_args_list]
        assert "#j_password" in fill_selectors, (
            f"Expected #j_password selector, got {fill_selectors}. "
            "j_password must come before #password in the selector list."
        )

    @pytest.mark.asyncio
    async def test_does_not_raise_when_no_selectors_match(self):
        """_try_sso_login must never raise — unmatched selectors are silently skipped."""
        from sourcing_agent.databases.browser_scraper import _try_sso_login

        # Completely empty page — no selectors match
        await _try_sso_login(_page(), "user", "pass", "Web of Science")

    @pytest.mark.asyncio
    async def test_does_not_raise_on_wait_timeout(self):
        """A timeout in wait_for_load_state must be caught, not propagated."""
        from sourcing_agent.databases.browser_scraper import _try_sso_login

        page = _page()
        # Simulate a Playwright timeout with a plain Exception — _try_sso_login
        # catches the base Exception class, so the exact type does not matter.
        page.wait_for_load_state.side_effect = Exception("Timeout 15000ms exceeded")

        # Must complete without raising
        await _try_sso_login(page, "user", "pass", "Web of Science")


# ═════════════════════════════════════════════════════════════════════════════
# 4. _save_session
# ═════════════════════════════════════════════════════════════════════════════


class TestSaveSession:
    @pytest.mark.asyncio
    async def test_calls_storage_state_with_correct_path(self, tmp_path):
        from sourcing_agent.databases.browser_scraper import _save_session

        ctx = AsyncMock()
        ctx.storage_state = AsyncMock()

        with patch("sourcing_agent.databases.browser_scraper._SESSION_DIR", tmp_path):
            await _save_session(ctx, "Web of Science")

        ctx.storage_state.assert_awaited_once()
        saved_path = ctx.storage_state.call_args.kwargs["path"]
        assert saved_path.endswith(
            "web_of_science_session.json"
        ), f"Session file path should end with web_of_science_session.json, got {saved_path}"

    @pytest.mark.asyncio
    async def test_creates_session_directory(self, tmp_path):
        from sourcing_agent.databases.browser_scraper import _save_session

        ctx = AsyncMock()
        ctx.storage_state = AsyncMock()
        session_dir = tmp_path / "auth"
        assert not session_dir.exists()

        with patch(
            "sourcing_agent.databases.browser_scraper._SESSION_DIR", session_dir
        ):
            await _save_session(ctx, "Scopus")

        assert session_dir.exists(), "Session directory must be created if absent"

    @pytest.mark.asyncio
    async def test_does_not_raise_when_storage_state_fails(self):
        """A failed save must log a warning, never crash the pipeline."""
        from sourcing_agent.databases.browser_scraper import _save_session

        ctx = AsyncMock()
        ctx.storage_state.side_effect = RuntimeError("disk full")

        # Must complete without raising
        await _save_session(ctx, "Web of Science")


# ═════════════════════════════════════════════════════════════════════════════
# 5. Scraper URL construction
# ═════════════════════════════════════════════════════════════════════════════
#
# The core bug: each scraper was hardcoding the direct vendor URL (e.g.
# https://www.webofscience.com/...) after SSO login had established a session
# on the proxy domain, thereby discarding the authenticated session.
#
# Fix: scrapers now accept `search_base` and construct URLs relative to it.
# These tests verify that navigated URLs use the supplied base, never a
# hardcoded direct vendor URL.


class TestScraperUrlConstruction:

    # ── Web of Science ────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_wos_navigates_to_proxy_relative_url(self):
        from sourcing_agent.databases.browser_scraper import _scrape_wos

        page = _page()  # no search box → early return after goto
        await _scrape_wos(page, "test query", _db_config("Web of Science"), _WOS_PROXY)

        goto_url = page.goto.call_args.args[0]
        assert (
            goto_url == f"{_WOS_PROXY}/wos/woscc/advanced-search"
        ), f"WoS must navigate via proxy base. Got: {goto_url!r}"

    @pytest.mark.asyncio
    async def test_wos_does_not_use_hardcoded_direct_url(self):
        from sourcing_agent.databases.browser_scraper import _scrape_wos

        page = _page()
        await _scrape_wos(page, "test query", _db_config("Web of Science"), _WOS_PROXY)

        goto_url = page.goto.call_args.args[0]
        assert "www.webofscience.com" not in goto_url, (
            "WoS scraper must NOT navigate to www.webofscience.com — "
            "this discards the EZProxy auth session. "
            f"Actual goto URL: {goto_url!r}"
        )

    @pytest.mark.asyncio
    async def test_wos_default_base_is_direct_url(self):
        """Without a proxy, the direct vendor URL is the correct fallback."""
        from sourcing_agent.databases.browser_scraper import _scrape_wos

        page = _page()
        await _scrape_wos(page, "test query", _db_config("Web of Science"))

        goto_url = page.goto.call_args.args[0]
        assert (
            goto_url == "https://www.webofscience.com/wos/woscc/advanced-search"
        ), f"Default (no-proxy) WoS URL should be the direct vendor URL. Got: {goto_url!r}"

    # ── Scopus ────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_scopus_navigates_to_proxy_relative_url(self):
        from sourcing_agent.databases.browser_scraper import _scrape_scopus

        page = _page()
        await _scrape_scopus(page, "test query", _db_config("Scopus"), _SCOPUS_PROXY)

        goto_url = page.goto.call_args.args[0]
        assert (
            goto_url == f"{_SCOPUS_PROXY}/search/form.uri?display=advanced"
        ), f"Scopus must navigate via proxy base. Got: {goto_url!r}"

    @pytest.mark.asyncio
    async def test_scopus_does_not_use_hardcoded_direct_url(self):
        from sourcing_agent.databases.browser_scraper import _scrape_scopus

        page = _page()
        await _scrape_scopus(page, "test query", _db_config("Scopus"), _SCOPUS_PROXY)

        goto_url = page.goto.call_args.args[0]
        assert "www.scopus.com" not in goto_url, (
            "Scopus scraper must NOT navigate to www.scopus.com — "
            "this discards the EZProxy auth session. "
            f"Actual goto URL: {goto_url!r}"
        )

    @pytest.mark.asyncio
    async def test_scopus_default_base_is_direct_url(self):
        from sourcing_agent.databases.browser_scraper import _scrape_scopus

        page = _page()
        await _scrape_scopus(page, "test query", _db_config("Scopus"))

        goto_url = page.goto.call_args.args[0]
        assert goto_url.startswith(
            "https://www.scopus.com/"
        ), f"Default Scopus URL should be the direct vendor URL. Got: {goto_url!r}"

    # ── IEEE Xplore ───────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_ieee_navigates_to_proxy_relative_url(self):
        from sourcing_agent.databases.browser_scraper import _scrape_ieee

        page = _page()
        await _scrape_ieee(
            page, "SLAM navigation", _db_config("IEEE Xplore"), _IEEE_PROXY
        )

        goto_url = page.goto.call_args.args[0]
        assert goto_url.startswith(
            _IEEE_PROXY
        ), f"IEEE must navigate via proxy base {_IEEE_PROXY!r}. Got: {goto_url!r}"

    @pytest.mark.asyncio
    async def test_ieee_does_not_use_hardcoded_direct_url(self):
        from sourcing_agent.databases.browser_scraper import _scrape_ieee

        page = _page()
        await _scrape_ieee(
            page, "SLAM navigation", _db_config("IEEE Xplore"), _IEEE_PROXY
        )

        goto_url = page.goto.call_args.args[0]
        assert "ieeexplore.ieee.org" not in goto_url, (
            "IEEE scraper must NOT navigate to ieeexplore.ieee.org — "
            "this discards the EZProxy auth session. "
            f"Actual goto URL: {goto_url!r}"
        )

    @pytest.mark.asyncio
    async def test_ieee_embeds_query_in_url(self):
        """IEEE Xplore takes the query as a URL parameter, not a form field."""
        from urllib.parse import quote_plus

        from sourcing_agent.databases.browser_scraper import _scrape_ieee

        page = _page()
        query = "autonomous robot navigation"
        await _scrape_ieee(page, query, _db_config("IEEE Xplore"), _IEEE_PROXY)

        goto_url = page.goto.call_args.args[0]
        assert (
            quote_plus(query) in goto_url or query.replace(" ", "+") in goto_url
        ), f"Expected query in URL. Got: {goto_url!r}"

    @pytest.mark.asyncio
    async def test_ieee_default_base_is_direct_url(self):
        from sourcing_agent.databases.browser_scraper import _scrape_ieee

        page = _page()
        await _scrape_ieee(page, "test", _db_config("IEEE Xplore"))

        goto_url = page.goto.call_args.args[0]
        assert goto_url.startswith(
            "https://ieeexplore.ieee.org/"
        ), f"Default IEEE URL should be the direct vendor URL. Got: {goto_url!r}"


# ═════════════════════════════════════════════════════════════════════════════
# 6. _get_authenticated_context — Option B → Option A fallback chain
# ═════════════════════════════════════════════════════════════════════════════


class TestGetAuthenticatedContext:
    """Tests for the two-path authentication strategy.

    Option B (saved session) is tried first.  If the loaded session lands on a
    login page (session expired) the context is closed and Option A (SSO) runs.
    All paths return the proxy root as search_base when proxy_url is set.
    """

    def _make_browser(self, *contexts: AsyncMock) -> AsyncMock:
        """Return a mock browser whose new_context returns contexts in order."""
        browser = AsyncMock()
        browser.new_context = AsyncMock(side_effect=list(contexts))
        return browser

    def _make_context(self, page: AsyncMock | None = None) -> AsyncMock:
        ctx = AsyncMock()
        ctx.close = AsyncMock()
        ctx.storage_state = AsyncMock()
        ctx.new_page = AsyncMock(return_value=(page or _page()))
        return ctx

    # ── Option B: valid saved session ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_option_b_uses_saved_session_when_valid(self, tmp_path):
        """A valid saved session file must be loaded; SSO must not be called."""
        from sourcing_agent.databases.browser_scraper import _get_authenticated_context

        session_file = tmp_path / "web_of_science_session.json"
        session_file.write_text("{}")

        ctx_b = self._make_context()
        browser = self._make_browser(ctx_b)

        with (
            patch(
                "sourcing_agent.databases.browser_scraper._session_path",
                return_value=session_file,
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._is_on_login_page",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._try_sso_login",
                new=AsyncMock(),
            ) as mock_sso,
        ):
            returned_ctx, _base = await _get_authenticated_context(
                browser, _db_config("Web of Science"), "user", "pass", _WOS_PROXY
            )

        assert returned_ctx is ctx_b, "Option B context must be returned unchanged"
        mock_sso.assert_not_awaited()  # SSO must not run when session is valid

    @pytest.mark.asyncio
    async def test_option_b_loads_storage_state_from_file(self, tmp_path):
        """browser.new_context must be called with storage_state= pointing to the session file."""
        from sourcing_agent.databases.browser_scraper import _get_authenticated_context

        session_file = tmp_path / "web_of_science_session.json"
        session_file.write_text("{}")

        ctx_b = self._make_context()
        browser = self._make_browser(ctx_b)

        with (
            patch(
                "sourcing_agent.databases.browser_scraper._session_path",
                return_value=session_file,
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._is_on_login_page",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._try_sso_login",
                new=AsyncMock(),
            ),
        ):
            await _get_authenticated_context(
                browser, _db_config("Web of Science"), "user", "pass", _WOS_PROXY
            )

        first_call_kwargs = browser.new_context.call_args_list[0].kwargs
        assert "storage_state" in first_call_kwargs, (
            "Option B must call browser.new_context(storage_state=...). "
            f"Actual kwargs: {first_call_kwargs}"
        )
        assert first_call_kwargs["storage_state"] == str(session_file)

    # ── Option B: expired session falls back to Option A ─────────────────────

    @pytest.mark.asyncio
    async def test_option_b_falls_back_to_sso_when_session_expired(self, tmp_path):
        """When the loaded session lands on a login page, SSO must be attempted."""
        from sourcing_agent.databases.browser_scraper import _get_authenticated_context

        session_file = tmp_path / "web_of_science_session.json"
        session_file.write_text("{}")

        ctx_b = self._make_context()
        ctx_a = self._make_context()
        # Two new_page() calls for Option A: sso_page and verify_page
        ctx_a.new_page = AsyncMock(side_effect=[_page(), _page()])
        browser = self._make_browser(ctx_b, ctx_a)

        with (
            patch(
                "sourcing_agent.databases.browser_scraper._session_path",
                return_value=session_file,
            ),
            # Session probe sees a login page → session expired
            patch(
                "sourcing_agent.databases.browser_scraper._is_on_login_page",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._try_sso_login",
                new=AsyncMock(),
            ) as mock_sso,
            patch(
                "sourcing_agent.databases.browser_scraper._save_session",
                new=AsyncMock(),
            ),
        ):
            returned_ctx, _ = await _get_authenticated_context(
                browser, _db_config("Web of Science"), "user", "pass", _WOS_PROXY
            )

        ctx_b.close.assert_awaited_once()  # expired context must be closed
        mock_sso.assert_awaited_once()  # SSO must run as fallback
        assert returned_ctx is ctx_a, "Option A context must be returned after fallback"

    @pytest.mark.asyncio
    async def test_expired_session_context_is_closed_before_option_a(self, tmp_path):
        """The Option B context must be closed (not leaked) before Option A runs."""
        from sourcing_agent.databases.browser_scraper import _get_authenticated_context

        session_file = tmp_path / "web_of_science_session.json"
        session_file.write_text("{}")

        closed_before_sso: list[bool] = []
        ctx_b = self._make_context()
        ctx_a = self._make_context()
        ctx_a.new_page = AsyncMock(side_effect=[_page(), _page()])

        async def mock_sso(*args, **kwargs):
            closed_before_sso.append(ctx_b.close.called)

        browser = self._make_browser(ctx_b, ctx_a)

        with (
            patch(
                "sourcing_agent.databases.browser_scraper._session_path",
                return_value=session_file,
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._is_on_login_page",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._try_sso_login", new=mock_sso
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._save_session",
                new=AsyncMock(),
            ),
        ):
            await _get_authenticated_context(
                browser, _db_config("Web of Science"), "user", "pass", _WOS_PROXY
            )

        assert closed_before_sso == [
            True
        ], "Option B context must be closed before SSO login is attempted"

    # ── No session file → straight to Option A ────────────────────────────────

    @pytest.mark.asyncio
    async def test_goes_directly_to_sso_when_no_session_file(self, tmp_path):
        """When no session file exists, skip Option B and run SSO immediately."""
        from sourcing_agent.databases.browser_scraper import _get_authenticated_context

        # Session file does NOT exist
        absent_session = tmp_path / "web_of_science_session.json"

        ctx_a = self._make_context()
        ctx_a.new_page = AsyncMock(side_effect=[_page(), _page()])
        browser = self._make_browser(ctx_a)

        with (
            patch(
                "sourcing_agent.databases.browser_scraper._session_path",
                return_value=absent_session,
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._is_on_login_page",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._try_sso_login",
                new=AsyncMock(),
            ) as mock_sso,
            patch(
                "sourcing_agent.databases.browser_scraper._save_session",
                new=AsyncMock(),
            ),
        ):
            await _get_authenticated_context(
                browser, _db_config("Web of Science"), "user", "pass", _WOS_PROXY
            )

        # Only one new_context call — no storage_state (Option B skipped)
        assert browser.new_context.call_count == 1
        call_kwargs = browser.new_context.call_args.kwargs
        assert "storage_state" not in call_kwargs, (
            "Without a session file, new_context must NOT be called with storage_state. "
            f"Actual kwargs: {call_kwargs}"
        )
        mock_sso.assert_awaited_once()

    # ── search_base is always the proxy root ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_search_base_is_proxy_url_in_option_b(self, tmp_path):
        from sourcing_agent.databases.browser_scraper import _get_authenticated_context

        session_file = tmp_path / "web_of_science_session.json"
        session_file.write_text("{}")

        ctx_b = self._make_context()
        browser = self._make_browser(ctx_b)

        with (
            patch(
                "sourcing_agent.databases.browser_scraper._session_path",
                return_value=session_file,
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._is_on_login_page",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._try_sso_login",
                new=AsyncMock(),
            ),
        ):
            _, base = await _get_authenticated_context(
                browser, _db_config("Web of Science"), "user", "pass", _WOS_PROXY
            )

        assert base == _WOS_PROXY, f"search_base must be the proxy root. Got: {base!r}"

    @pytest.mark.asyncio
    async def test_search_base_is_proxy_url_in_option_a(self, tmp_path):
        from sourcing_agent.databases.browser_scraper import _get_authenticated_context

        absent_session = tmp_path / "web_of_science_session.json"

        ctx_a = self._make_context()
        ctx_a.new_page = AsyncMock(side_effect=[_page(), _page()])
        browser = self._make_browser(ctx_a)

        with (
            patch(
                "sourcing_agent.databases.browser_scraper._session_path",
                return_value=absent_session,
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._is_on_login_page",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._try_sso_login",
                new=AsyncMock(),
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._save_session",
                new=AsyncMock(),
            ),
        ):
            _, base = await _get_authenticated_context(
                browser, _db_config("Web of Science"), "user", "pass", _WOS_PROXY
            )

        assert (
            base == _WOS_PROXY
        ), f"search_base must be the proxy root even via Option A. Got: {base!r}"

    # ── Option A saves session after confirmed auth ────────────────────────────

    @pytest.mark.asyncio
    async def test_option_a_saves_session_after_successful_login(self, tmp_path):
        """After SSO login is confirmed, the session must be persisted for future Option B use."""
        from sourcing_agent.databases.browser_scraper import _get_authenticated_context

        absent_session = tmp_path / "web_of_science_session.json"
        ctx_a = self._make_context()
        ctx_a.new_page = AsyncMock(side_effect=[_page(), _page()])
        browser = self._make_browser(ctx_a)

        with (
            patch(
                "sourcing_agent.databases.browser_scraper._session_path",
                return_value=absent_session,
            ),
            # verify page is NOT on login page → login succeeded
            patch(
                "sourcing_agent.databases.browser_scraper._is_on_login_page",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._try_sso_login",
                new=AsyncMock(),
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._save_session",
                new=AsyncMock(),
            ) as mock_save,
        ):
            await _get_authenticated_context(
                browser, _db_config("Web of Science"), "user", "pass", _WOS_PROXY
            )

        mock_save.assert_awaited_once(), (
            "_save_session must be called after successful SSO login "
            "so the next run can use the Option B fast path"
        )

    @pytest.mark.asyncio
    async def test_option_a_does_not_save_session_when_still_on_login_page(
        self, tmp_path
    ):
        """If SSO login fails (still on login page), do NOT save the useless session."""
        from sourcing_agent.databases.browser_scraper import _get_authenticated_context

        absent_session = tmp_path / "web_of_science_session.json"
        ctx_a = self._make_context()
        ctx_a.new_page = AsyncMock(side_effect=[_page(), _page()])
        browser = self._make_browser(ctx_a)

        with (
            patch(
                "sourcing_agent.databases.browser_scraper._session_path",
                return_value=absent_session,
            ),
            # verify page IS still on login page → SSO failed
            patch(
                "sourcing_agent.databases.browser_scraper._is_on_login_page",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._try_sso_login",
                new=AsyncMock(),
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._save_session",
                new=AsyncMock(),
            ) as mock_save,
        ):
            await _get_authenticated_context(
                browser, _db_config("Web of Science"), "user", "pass", _WOS_PROXY
            )

        mock_save.assert_not_awaited(), (
            "_save_session must NOT be called when SSO login failed "
            "(page is still on the login form)"
        )

    # ── SSO navigates to proxy URL, not direct URL ────────────────────────────

    @pytest.mark.asyncio
    async def test_option_a_navigates_sso_page_to_proxy_url(self, tmp_path):
        """SSO login must start at the institutional proxy URL, not the vendor site."""
        from sourcing_agent.databases.browser_scraper import _get_authenticated_context

        absent_session = tmp_path / "web_of_science_session.json"
        sso_page = _page()
        verify_page = _page()
        ctx_a = self._make_context()
        ctx_a.new_page = AsyncMock(side_effect=[sso_page, verify_page])
        browser = self._make_browser(ctx_a)

        with (
            patch(
                "sourcing_agent.databases.browser_scraper._session_path",
                return_value=absent_session,
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._is_on_login_page",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._try_sso_login",
                new=AsyncMock(),
            ),
            patch(
                "sourcing_agent.databases.browser_scraper._save_session",
                new=AsyncMock(),
            ),
        ):
            await _get_authenticated_context(
                browser, _db_config("Web of Science"), "user", "pass", _WOS_PROXY
            )

        # The SSO page (first new_page call) must be navigated to the proxy URL
        first_goto = sso_page.goto.call_args.args[0]
        assert (
            first_goto == _WOS_PROXY
        ), f"SSO must start at proxy URL {_WOS_PROXY!r}. Got: {first_goto!r}"
