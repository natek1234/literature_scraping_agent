from __future__ import annotations

import asyncio
import datetime
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from loguru import logger

from ..config import Config, DatabaseConfig
from ..models import PaperRecord

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Search page paths relative to each database's root (proxy or direct).
# WoS and Scopus use advanced search pages that accept field-tagged query syntax
# (TS= for WoS, TITLE-ABS-KEY() for Scopus) — basic search pages do not.
_SEARCH_PATHS: dict[str, str] = {
    "Web of Science": "/wos/woscc/advanced-search",
    "Scopus": "/search/form.uri?display=advanced",
    "IEEE Xplore": "/search/searchresult.jsp",
    "ACM Digital Library": "/search/",
}

# Direct (non-proxy) base URLs — fallback when no proxy is configured
_DIRECT_BASES: dict[str, str] = {
    "Web of Science": "https://www.webofscience.com",
    "Scopus": "https://www.scopus.com",
    "IEEE Xplore": "https://ieeexplore.ieee.org",
    "ACM Digital Library": "https://dl.acm.org",
}

# Saved browser session files (Option B). outputs/ is already in .gitignore.
_SESSION_DIR = Path("outputs/.auth")


# ── Public entry point ────────────────────────────────────────────────────────


async def search(
    db_config: DatabaseConfig, query: str, config: Config
) -> list[PaperRecord]:
    name = db_config.name
    cred_env = db_config.credential_env_vars

    username = os.environ.get(cred_env.get("username", ""), "")
    password = os.environ.get(cred_env.get("password", ""), "")
    proxy_url = (
        os.environ.get(cred_env.get("proxy_url", ""), "")
        if cred_env.get("proxy_url")
        else ""
    )

    _PLACEHOLDERS = ("your_email", "your_password", "placeholder", "institution.edu")
    if not username or not password:
        logger.warning(
            f"{name}: credentials missing "
            f"(env vars: {cred_env.get('username')}, {cred_env.get('password')}) — skipping"
        )
        return []
    if any(p in username for p in _PLACEHOLDERS) or any(
        p in password for p in _PLACEHOLDERS
    ):
        logger.warning(f"{name}: placeholder credentials detected — skipping")
        return []
    if proxy_url and "your-institution" in proxy_url:
        logger.warning(f"{name}: proxy URL is a placeholder — skipping")
        return []

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error(f"{name}: playwright not installed — skipping")
        return []

    if name not in _SEARCH_PATHS:
        logger.warning(f"{name}: no URL configured — skipping")
        return []

    records: list[PaperRecord] = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context, search_base = await _get_authenticated_context(
                    browser, db_config, username, password, proxy_url
                )
                page = await context.new_page()
                try:
                    records = await _scrape_db(
                        page, name, search_base, query, db_config, config
                    )
                    # Refresh saved session after successful scraping (servers
                    # often update cookie expiry on use, so re-saving keeps the
                    # Option B session alive longer).
                    await _save_session(context, name)
                except Exception as exc:
                    logger.error(f"{name}: scraping error — {exc}")
                finally:
                    await page.close()
                    await context.close()
            finally:
                await browser.close()
    except Exception as exc:
        logger.error(f"{name}: playwright launch failed — {exc}")

    logger.info(f"{name}: '{query[:60]}' → {len(records)} records")
    return records


async def search_batch(
    db_config: DatabaseConfig, queries: list[str], config: Config
) -> list[PaperRecord]:
    """Execute all queries for one database inside a single browser session.

    A single browser launch means the EZProxy session cookie is reused for
    every query, preventing the ~15-minute wall-clock expiry that occurs when
    each query spawns its own browser process.  The session file is refreshed
    after every successful query so it stays alive as long as possible.
    """
    name = db_config.name
    cred_env = db_config.credential_env_vars

    username = os.environ.get(cred_env.get("username", ""), "")
    password = os.environ.get(cred_env.get("password", ""), "")
    proxy_url = (
        os.environ.get(cred_env.get("proxy_url", ""), "")
        if cred_env.get("proxy_url")
        else ""
    )

    _PLACEHOLDERS = ("your_email", "your_password", "placeholder", "institution.edu")
    if not username or not password:
        logger.warning(
            f"{name}: credentials missing "
            f"(env vars: {cred_env.get('username')}, {cred_env.get('password')}) — skipping"
        )
        return []
    if any(p in username for p in _PLACEHOLDERS) or any(
        p in password for p in _PLACEHOLDERS
    ):
        logger.warning(f"{name}: placeholder credentials detected — skipping")
        return []
    if proxy_url and "your-institution" in proxy_url:
        logger.warning(f"{name}: proxy URL is a placeholder — skipping")
        return []

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error(f"{name}: playwright not installed — skipping")
        return []

    if name not in _SEARCH_PATHS:
        logger.warning(f"{name}: no URL configured — skipping")
        return []

    all_records: list[PaperRecord] = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context, search_base = await _get_authenticated_context(
                browser, db_config, username, password, proxy_url
            )
            remaining = list(enumerate(queries))
            while remaining:
                idx, query = remaining[0]
                remaining = remaining[1:]
                page = await context.new_page()
                expired = False
                try:
                    records = await _scrape_db(
                        page, name, search_base, query, db_config, config
                    )

                    # Mid-run session expiry: 0 results AND page is a login form
                    if not records and await _is_on_login_page(page):
                        logger.warning(
                            f"{name}: session expired at query {idx + 1} "
                            "— prompting re-authentication"
                        )
                        expired = True
                    else:
                        all_records.extend(records)
                        logger.info(
                            f"{name}: query {idx + 1}/{len(queries)} "
                            f"→ {len(records)} records"
                        )
                        await _save_session(context, name)
                except Exception as exc:
                    logger.error(
                        f"{name}: query {idx + 1}/{len(queries)} failed — {exc}"
                    )
                finally:
                    await page.close()

                if expired:
                    # Close stale browser, prompt fresh login, reopen headless
                    await context.close()
                    await browser.close()
                    await prompt_and_save_session(name, proxy_url)
                    browser = await p.chromium.launch(headless=True)
                    context, search_base = await _get_authenticated_context(
                        browser, db_config, username, password, proxy_url
                    )
                    # Put the failed query back at the front so it is retried
                    remaining = [(idx, query), *remaining]
                    continue

                if remaining:
                    await asyncio.sleep(3)

            await browser.close()
    except Exception as exc:
        logger.error(f"{name}: playwright launch failed — {exc}")

    logger.info(
        f"{name}: batch complete — {len(all_records)} total records "
        f"from {len(queries)} queries"
    )
    return all_records


# ── Authentication: Option B → Option A ──────────────────────────────────────


async def _get_authenticated_context(
    browser: Any,
    db_config: DatabaseConfig,
    username: str,
    password: str,
    proxy_url: str,
) -> tuple[Any, str]:
    """
    Return ``(BrowserContext, search_base_url)``.

    ``search_base_url`` is the URL root from which each scraper appends its
    database-specific search path (e.g. ``/wos/woscc/basic-search``).

    Authentication strategy — in order:

    Option B (fast path)
        Load a saved ``outputs/.auth/<db>_session.json`` file.  Navigate to
        the search page and confirm we are *not* on a login form.  If the
        session is still valid, return immediately — no SSO automation needed.

    Option A (SSO automation)
        Open a fresh browser context, navigate to the institutional proxy URL,
        and fill the login form (UofA Shibboleth selectors first, then generic
        fallbacks).  After login, navigate to the search page to verify
        authentication succeeded and persist the new session so the next call
        takes the Option B fast path.
    """
    from playwright.async_api import Browser

    assert isinstance(browser, Browser)

    name = db_config.name
    search_path = _SEARCH_PATHS[name]
    base = proxy_url.rstrip("/") if proxy_url else _DIRECT_BASES.get(name, "")
    search_url = f"{base}{search_path}"
    session_file = _session_path(name)

    # ── Option B: try saved session ───────────────────────────────────────────
    if session_file.exists():
        logger.debug(f"{name}: trying saved session — {session_file} (Option B)")
        try:
            ctx = await browser.new_context(
                storage_state=str(session_file),
                user_agent=_USER_AGENT,
            )
            probe = await ctx.new_page()
            try:
                await probe.goto(search_url, timeout=30000)
                await probe.wait_for_load_state("networkidle", timeout=20000)
                on_login = await _is_on_login_page(probe)
            finally:
                await probe.close()

            if not on_login:
                logger.info(f"{name}: saved session is valid — using Option B")
                return ctx, base

            logger.info(
                f"{name}: saved session has expired — falling back to SSO (Option A)"
            )
            await ctx.close()

        except Exception as exc:
            logger.warning(
                f"{name}: Option B failed ({exc}) — falling back to SSO (Option A)"
            )

    # ── Option A: SSO login via proxy ─────────────────────────────────────────
    logger.info(f"{name}: starting SSO login (Option A)")
    ctx = await browser.new_context(user_agent=_USER_AGENT)

    if proxy_url:
        sso_page = await ctx.new_page()
        try:
            await sso_page.goto(proxy_url, timeout=30000)
            await asyncio.sleep(3)
            await _try_sso_login(sso_page, username, password, name)
        except Exception as exc:
            logger.warning(f"{name}: SSO navigation error — {exc}")
        finally:
            await sso_page.close()

        # Verify login succeeded and persist session for next run
        verify = await ctx.new_page()
        try:
            await verify.goto(search_url, timeout=30000)
            await verify.wait_for_load_state("networkidle", timeout=20000)
            if not await _is_on_login_page(verify):
                logger.info(
                    f"{name}: SSO login confirmed — saving session for Option B"
                )
                await _save_session(ctx, name)
            else:
                logger.warning(
                    f"{name}: still on login page after SSO attempt — "
                    "check credentials or MFA requirement"
                )
        except Exception as exc:
            logger.warning(f"{name}: post-login verification failed — {exc}")
        finally:
            await verify.close()

    return ctx, base


async def _is_on_login_page(page: Any) -> bool:
    """Return True if the current page is an SSO/login form OR a Duo MFA prompt.

    Duo MFA selectors are included so that a session captured mid-MFA challenge
    is never written to disk — preserving the original valid session file.
    """
    from playwright.async_api import Page

    assert isinstance(page, Page)

    login_selectors = [
        "#j_username",  # UofA Shibboleth / standard SAML
        'input[name="j_username"]',
        "#netid",
        'input[name="netid"]',
        "#username",
        'input[name="username"]',
        'input[type="email"][autocomplete="username"]',
        # Duo MFA — cannot be automated; treat as auth-not-complete
        "#duo_iframe",
        'iframe[data-dashtype="prompt"]',
        ".duo-frame",
        'iframe[title*="Duo" i]',
        "#duo-submit-btn",
    ]
    for sel in login_selectors:
        if await page.query_selector(sel):
            return True
    return False


async def _try_sso_login(page: Any, username: str, password: str, db_name: str) -> None:
    """
    Fill and submit an institutional SSO form.

    Selector priority: UofA Shibboleth (``j_username`` / ``j_password``) first,
    then generic fallbacks.  Detects Duo MFA and logs a clear warning rather
    than raising, so the pipeline can continue with other databases.
    """
    from playwright.async_api import Page

    assert isinstance(page, Page)

    try:
        await page.wait_for_load_state("networkidle", timeout=15000)

        for sel in (
            "#j_username",
            'input[name="j_username"]',
            "#netid",
            'input[name="netid"]',
            "#username",
            'input[name="username"]',
            'input[type="email"]',
        ):
            if await page.query_selector(sel):
                await page.fill(sel, username)
                break

        for sel in (
            "#j_password",
            'input[name="j_password"]',
            "#password",
            'input[name="password"]',
            'input[type="password"]',
        ):
            if await page.query_selector(sel):
                await page.fill(sel, password)
                break

        for sel in ('button[type="submit"]', 'input[type="submit"]', "#submit"):
            if await page.query_selector(sel):
                await page.click(sel)
                break

        await page.wait_for_load_state("networkidle", timeout=20000)

        # Detect Duo MFA — cannot be automated; steer user to Option B
        if await page.query_selector(
            "#duo_iframe, iframe[data-dashtype='prompt'], .duo-frame"
        ):
            logger.warning(
                f"{db_name}: Duo MFA prompt detected — automated SSO cannot "
                "proceed past MFA. Log in manually once in a headed browser, "
                "then run: python outputs/save_browser_session.py"
            )

    except Exception as exc:
        logger.warning(f"{db_name}: SSO login attempt failed — {exc}")


# ── Session persistence helpers ───────────────────────────────────────────────


def _session_path(db_name: str) -> Path:
    slug = db_name.lower().replace(" ", "_")
    return _SESSION_DIR / f"{slug}_session.json"


async def _save_session(context: Any, db_name: str) -> None:
    """Persist browser cookies and storage state to disk (enables Option B on next run)."""
    from playwright.async_api import BrowserContext

    assert isinstance(context, BrowserContext)

    _SESSION_DIR.mkdir(parents=True, exist_ok=True)
    path = _session_path(db_name)
    try:
        await context.storage_state(path=str(path))
        logger.debug(f"{db_name}: session saved → {path}")
    except Exception as exc:
        logger.warning(f"{db_name}: could not save session — {exc}")


async def prompt_and_save_session(db_name: str, proxy_url: str) -> None:
    """Ensure a fresh browser session for db_name before querying.

    TTY mode (interactive terminal): opens a headed Chromium window, waits
    for the user to complete SSO + Duo MFA, then saves the session.

    Non-TTY mode (IDE/subprocess): prints instructions asking the user to
    run ``scripts/save_browser_session.py`` in their own terminal, then
    polls for the session file every 5 seconds and resumes automatically
    once a fresh session (< 5 min old) is detected.  Times out after 10 min.
    """
    import sys as _sys
    import time as _time

    if not _sys.stdin.isatty():
        # ── Non-interactive: instruct + poll ────────────────────────────────
        session_file = _session_path(db_name)
        print(
            f"\n{'='*60}\n"
            f"  {db_name}: SSO authentication required.\n"
            f"\n"
            f"  In your terminal, run:\n"
            f"    python scripts/save_browser_session.py\n"
            f"  Select '{db_name}', complete SSO + Duo MFA,\n"
            f"  then press Enter in that window.\n"
            f"\n"
            f"  The pipeline will resume automatically once\n"
            f"  the session file is saved.\n"
            f"{'='*60}",
            flush=True,
        )
        _POLL_SEC = 5
        _TIMEOUT_SEC = 600  # 10 minutes
        for _ in range(_TIMEOUT_SEC // _POLL_SEC):
            await asyncio.sleep(_POLL_SEC)
            if session_file.exists():
                age = _time.time() - session_file.stat().st_mtime
                if age < 300:
                    logger.info(
                        f"{db_name}: session file detected "
                        f"({age:.0f}s old) — resuming"
                    )
                    return
        raise RuntimeError(
            f"{db_name}: timed out after "
            f"{_TIMEOUT_SEC // 60} min waiting for session file"
        )

    # ── Interactive TTY: open headed browser ────────────────────────────────
    from playwright.async_api import async_playwright

    search_path = _SEARCH_PATHS.get(db_name, "/")
    base = proxy_url.rstrip("/") if proxy_url else _DIRECT_BASES.get(db_name, "")
    start_url = f"{base}{search_path}"

    print(
        f"\n{'='*60}\n"
        f"  Auth required: {db_name}\n"
        f"  Opening: {start_url}\n"
        f"  1. Log in (SSO + Duo MFA if prompted)\n"
        f"  2. Navigate to the search/advanced-search page\n"
        f"  3. Press Enter here once you are on the search page\n"
        f"{'='*60}"
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        try:
            context = await browser.new_context(user_agent=_USER_AGENT)
            page = await context.new_page()
            await page.goto(start_url, timeout=60_000)
            input("  [Press Enter once you are on the search page] ")
            await _save_session(context, db_name)
            logger.info(f"{db_name}: fresh session saved via prompted login")
        finally:
            await browser.close()


# ── Dispatcher ────────────────────────────────────────────────────────────────


async def _scrape_db(
    page: Any,
    name: str,
    search_base: str,
    query: str,
    db_config: DatabaseConfig,
    config: Config,
) -> list[PaperRecord]:
    from playwright.async_api import Page

    assert isinstance(page, Page)

    if name == "Web of Science":
        return await _scrape_wos(page, query, db_config, search_base)
    elif name == "Scopus":
        return await _scrape_scopus(page, query, db_config, search_base)
    elif name == "IEEE Xplore":
        return await _scrape_ieee(page, query, db_config, search_base)
    elif name == "ACM Digital Library":
        return await _scrape_acm(page, query, db_config)
    return []


# ── Per-database scrapers ─────────────────────────────────────────────────────


async def _scrape_wos(
    page: Any,
    query: str,
    db_config: DatabaseConfig,
    search_base: str = "https://www.webofscience.com",
) -> list[PaperRecord]:
    """WoS advanced search — accepts TS= field-tagged query strings."""
    from playwright.async_api import Page

    assert isinstance(page, Page)

    records: list[PaperRecord] = []
    max_results = db_config.max_results_per_query
    search_url = f"{search_base.rstrip('/')}/wos/woscc/advanced-search"

    try:
        await page.goto(search_url, timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=20000)
        await asyncio.sleep(3)

        # Advanced search uses a textarea for the full query expression
        query_input = None
        for sel in (
            "textarea.mat-input-element",
            "#advancedSearchInputArea",
            'textarea[data-ng-model="advancedSearchQueryText"]',
            'textarea[placeholder*="Enter" i]',
            'textarea[aria-label*="search" i]',
            "textarea",
        ):
            if await page.query_selector(sel):
                query_input = sel
                break

        if not query_input:
            logger.warning(
                "Web of Science: advanced search textarea not found "
                "— authentication may have failed"
            )
            return []

        await page.fill(query_input, query)
        await asyncio.sleep(1)

        for btn_sel in (
            'button[data-ta="run-search"]',
            'button[aria-label*="Search" i]',
            'button[type="submit"]',
            ".search-button",
            'button:has-text("Search")',
        ):
            btn = await page.query_selector(btn_sel)
            if btn:
                await btn.click()
                break

        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)

        records = await _extract_wos_results(page, max_results)

    except Exception as exc:
        logger.error(f"WoS scraping error: {exc}")

    return records


async def _extract_wos_results(page: Any, max_results: int) -> list[PaperRecord]:
    from playwright.async_api import Page

    assert isinstance(page, Page)

    records: list[PaperRecord] = []
    try:
        result_items = await page.query_selector_all("app-record, .search-results-item")
        for item in result_items[:max_results]:
            try:
                title_el = await item.query_selector(".title, h3 a, .record-title")
                title = (await title_el.inner_text()).strip() if title_el else ""
                if not title:
                    continue

                authors_els = await item.query_selector_all(
                    ".authors .value, .author-name"
                )
                authors = [
                    (await el.inner_text()).strip()
                    for el in authors_els
                    if (await el.inner_text()).strip()
                ]

                year_el = await item.query_selector(".pub-year, .year")
                year_text = (await year_el.inner_text()) if year_el else ""
                year = _extract_year(year_text)

                venue_el = await item.query_selector(".source-title, .venue")
                venue = (await venue_el.inner_text()).strip() if venue_el else None

                records.append(
                    PaperRecord(
                        title=title,
                        authors=authors,
                        year=year,
                        venue=venue,
                        source_database="Web of Science",
                        retrieved_at=datetime.datetime.utcnow().isoformat(),
                    )
                )
            except Exception:
                continue
    except Exception as exc:
        logger.warning(f"WoS result extraction error: {exc}")

    return records


async def _scrape_scopus(
    page: Any,
    query: str,
    db_config: DatabaseConfig,
    search_base: str = "https://www.scopus.com",
) -> list[PaperRecord]:
    """Scopus advanced search — accepts TITLE-ABS-KEY() field-tagged queries."""
    from playwright.async_api import Page

    assert isinstance(page, Page)

    records: list[PaperRecord] = []
    max_results = db_config.max_results_per_query
    search_url = f"{search_base.rstrip('/')}/search/form.uri?display=advanced"

    try:
        await page.goto(search_url, timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=20000)
        await asyncio.sleep(3)

        filled = False

        # Strategy 1: plain textarea selectors (works when Scopus renders a
        # standard <textarea> for the advanced query box)
        for sel in (
            'textarea[id*="query" i]',
            'textarea[name*="query" i]',
            "#advancedSearchInput",
            "#queryField",
            'textarea[placeholder*="Enter" i]',
            'textarea[aria-label*="search" i]',
            'textarea[aria-label*="query" i]',
            "textarea",
        ):
            el = await page.query_selector(sel)
            if el:
                await page.fill(sel, query)
                filled = True
                logger.debug(f"Scopus: filled query via textarea selector '{sel}'")
                break

        # Strategy 2: CodeMirror editor — Scopus advanced search sometimes
        # renders a CodeMirror widget whose underlying <textarea> is hidden.
        # We set the value through the CodeMirror JavaScript API.
        if not filled:
            cm_set = await page.evaluate(
                """(query) => {
                    const cm = document.querySelector('.CodeMirror');
                    if (cm && cm.CodeMirror) {
                        cm.CodeMirror.setValue(query);
                        return true;
                    }
                    return false;
                }""",
                query,
            )
            if cm_set:
                filled = True
                logger.debug("Scopus: filled query via CodeMirror JS API")

        # Strategy 3: contenteditable div (React / draft.js patterns)
        if not filled:
            ce = await page.query_selector(
                '[contenteditable="true"][aria-label*="search" i], '
                '[contenteditable="true"][role="textbox"]'
            )
            if ce:
                await ce.click()
                await page.keyboard.press("Control+a")
                await page.keyboard.type(query)
                filled = True
                logger.debug("Scopus: filled query via contenteditable div")

        if not filled:
            # Dump visible input/textarea tags to help diagnose selector mismatches
            inputs = await page.evaluate("""() => {
                    const tags = ['input','textarea','[contenteditable]'];
                    return tags.flatMap(t =>
                        [...document.querySelectorAll(t)].map(el => ({
                            tag: el.tagName,
                            id: el.id,
                            name: el.name || '',
                            type: el.type || '',
                            placeholder: el.placeholder || '',
                            ariaLabel: el.getAttribute('aria-label') || ''
                        }))
                    );
                }""")
            logger.warning(
                f"Scopus: no query input found on advanced search page. "
                f"Visible inputs: {inputs}"
            )
            return []

        await asyncio.sleep(1)

        for btn_sel in (
            'button[data-testid="submit-search"]',
            'button[data-ta="run-search"]',
            'button[type="submit"]',
            "#searchBtn",
            'button:has-text("Search")',
        ):
            btn = await page.query_selector(btn_sel)
            if btn:
                await btn.click()
                break

        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)

        result_items = await page.query_selector_all(
            'article[data-testid="result-item"], .searchArea .resultRow, '
            'li[data-testid="result-item"]'
        )

        for item in result_items[:max_results]:
            try:
                title_el = await item.query_selector("h3 a, .documentTitle a")
                title = (await title_el.inner_text()).strip() if title_el else ""
                if not title:
                    continue

                authors_el = await item.query_selector(".authorNames, .authors")
                authors_text = (await authors_el.inner_text()) if authors_el else ""
                authors = [a.strip() for a in authors_text.split(",") if a.strip()]

                year_text = ""
                for year_sel in (".year", "span[data-testid='year']"):
                    el = await item.query_selector(year_sel)
                    if el:
                        year_text = await el.inner_text()
                        break
                year = _extract_year(year_text)

                venue_el = await item.query_selector(".sourceTitle, .publicationName")
                venue = (await venue_el.inner_text()).strip() if venue_el else None

                records.append(
                    PaperRecord(
                        title=title,
                        authors=authors,
                        year=year,
                        venue=venue,
                        source_database="Scopus",
                        retrieved_at=datetime.datetime.utcnow().isoformat(),
                    )
                )
            except Exception:
                continue

    except Exception as exc:
        logger.error(f"Scopus scraping error: {exc}")

    return records


async def _scrape_ieee(
    page: Any,
    query: str,
    db_config: DatabaseConfig,
    search_base: str = "https://ieeexplore.ieee.org",
) -> list[PaperRecord]:
    from playwright.async_api import Page

    assert isinstance(page, Page)

    records: list[PaperRecord] = []
    max_results = db_config.max_results_per_query
    search_url = (
        f"{search_base.rstrip('/')}/search/searchresult.jsp"
        f"?queryText={quote_plus(query)}"
    )

    try:
        await page.goto(search_url, timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=20000)
        await asyncio.sleep(3)

        result_items = await page.query_selector_all(
            ".List-results-items, .result-item"
        )
        for item in result_items[:max_results]:
            try:
                title_el = await item.query_selector("h2 a, .result-item-title a")
                title = (await title_el.inner_text()).strip() if title_el else ""
                if not title:
                    continue

                authors_el = await item.query_selector(".authors-info, .author")
                authors_text = (await authors_el.inner_text()) if authors_el else ""
                authors = [
                    a.strip() for a in re.split(r"[;,]", authors_text) if a.strip()
                ]

                year_text = ""
                year_el = await item.query_selector(
                    ".publisher-info-container, .article-footer-pub"
                )
                if year_el:
                    year_text = await year_el.inner_text()
                year = _extract_year(year_text)

                venue_el = await item.query_selector(".publication-title")
                venue = (await venue_el.inner_text()).strip() if venue_el else None

                doi_el = await item.query_selector('a[href*="doi"]')
                doi = None
                if doi_el:
                    href = await doi_el.get_attribute("href") or ""
                    m = re.search(r"10\.\d{4,}/\S+", href)
                    doi = m.group(0) if m else None

                records.append(
                    PaperRecord(
                        title=title,
                        authors=authors,
                        year=year,
                        venue=venue,
                        doi=doi,
                        source_database="IEEE Xplore",
                        retrieved_at=datetime.datetime.utcnow().isoformat(),
                    )
                )
            except Exception:
                continue

    except Exception as exc:
        logger.error(f"IEEE Xplore scraping error: {exc}")

    return records


async def _scrape_acm(
    page: Any,
    query: str,
    db_config: DatabaseConfig,
) -> list[PaperRecord]:
    """ACM Digital Library is open access — no proxy or session needed."""
    from playwright.async_api import Page

    assert isinstance(page, Page)

    records: list[PaperRecord] = []
    max_results = db_config.max_results_per_query

    try:
        await page.goto("https://dl.acm.org/search/", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=20000)
        await asyncio.sleep(3)

        for sel in (
            "#search-input",
            'input[name="AllField"]',
            'input[type="search"]',
        ):
            el = await page.query_selector(sel)
            if el:
                await page.fill(sel, query)
                break

        for btn_sel in ('button[type="submit"]', ".search-btn"):
            btn = await page.query_selector(btn_sel)
            if btn:
                await btn.click()
                break

        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)

        result_items = await page.query_selector_all("li.search__item")
        for item in result_items[:max_results]:
            try:
                title_el = await item.query_selector("h5.issue-item__title a")
                title = (await title_el.inner_text()).strip() if title_el else ""
                if not title:
                    continue

                authors_els = await item.query_selector_all(".hlFld-ContribAuthor")
                authors = [
                    (await el.inner_text()).strip()
                    for el in authors_els
                    if (await el.inner_text()).strip()
                ]

                year_text = ""
                date_el = await item.query_selector(".bookPubDate, .issue-item__detail")
                if date_el:
                    year_text = await date_el.inner_text()
                year = _extract_year(year_text)

                venue_el = await item.query_selector(".issue-item__detail em")
                venue = (await venue_el.inner_text()).strip() if venue_el else None

                doi_el = await item.query_selector('a[href*="/doi/"]')
                doi = None
                if doi_el:
                    href = await doi_el.get_attribute("href") or ""
                    m = re.search(r"10\.\d{4,}/\S+", href)
                    doi = m.group(0) if m else None

                records.append(
                    PaperRecord(
                        title=title,
                        authors=authors,
                        year=year,
                        venue=str(venue) if venue else None,
                        doi=doi,
                        source_database="ACM Digital Library",
                        retrieved_at=datetime.datetime.utcnow().isoformat(),
                    )
                )
            except Exception:
                continue

    except Exception as exc:
        logger.error(f"ACM DL scraping error: {exc}")

    return records


# ── Utilities ─────────────────────────────────────────────────────────────────


def _extract_year(text: str) -> int | None:
    m = re.search(r"\b(19|20)\d{2}\b", str(text))
    if m:
        try:
            return int(m.group(0))
        except ValueError:
            pass
    return None
