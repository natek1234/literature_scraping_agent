from __future__ import annotations

import asyncio
import datetime
import os
import re

from loguru import logger

from ..config import Config, DatabaseConfig
from ..models import PaperRecord

# URLs and search paths per database
_DB_URLS: dict[str, str] = {
    "IEEE Xplore": "https://ieeexplore.ieee.org/search/searchresult.jsp",
    "Web of Science": "https://www.webofscience.com/wos/woscc/basic-search",
    "Scopus": "https://www.scopus.com/search/form.uri",
    "ACM Digital Library": "https://dl.acm.org/search/",
}


async def search(
    db_config: DatabaseConfig, query: str, config: Config
) -> list[PaperRecord]:
    name = db_config.name
    cred_env = db_config.credential_env_vars

    username_key = cred_env.get("username", "")
    password_key = cred_env.get("password", "")
    proxy_key = cred_env.get("proxy_url", "")

    username = os.environ.get(username_key, "")
    password = os.environ.get(password_key, "")
    proxy_url = os.environ.get(proxy_key, "") if proxy_key else ""

    if not username or not password:
        logger.warning(
            f"{name}: credentials missing (env vars: {username_key}, {password_key}) — skipping"
        )
        return []

    # Skip placeholder proxy URLs (not configured for real institution)
    if proxy_url and "your-institution" in proxy_url:
        logger.warning(
            f"{name}: proxy URL is a placeholder — skipping (update .env with real proxy)"
        )
        return []

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error(f"{name}: playwright not installed — skipping")
        return []

    db_url = _DB_URLS.get(name, "")
    if not db_url:
        logger.warning(f"{name}: no URL configured — skipping")
        return []

    records: list[PaperRecord] = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()
            try:
                if proxy_url:
                    await page.goto(proxy_url, timeout=30000)
                    await asyncio.sleep(3)
                    await _try_login(page, username, password, name)

                records = await _scrape_db(page, name, db_url, query, db_config, config)

            except Exception as e:
                logger.error(f"{name}: scraping error — {e}")
            finally:
                await browser.close()

    except Exception as e:
        logger.error(f"{name}: playwright launch failed — {e}")

    logger.info(f"{name}: '{query[:60]}' → {len(records)} records")
    return records


async def _try_login(page: object, username: str, password: str, db_name: str) -> None:
    """Attempt SSO login — handles common form patterns."""
    from playwright.async_api import Page

    assert isinstance(page, Page)
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
        for sel in ("#username", 'input[name="username"]', 'input[type="email"]'):
            if await page.query_selector(sel):
                await page.fill(sel, username)
                break
        for sel in ("#password", 'input[name="password"]', 'input[type="password"]'):
            if await page.query_selector(sel):
                await page.fill(sel, password)
                break
        for sel in ('button[type="submit"]', 'input[type="submit"]', "#submit"):
            if await page.query_selector(sel):
                await page.click(sel)
                break
        await page.wait_for_load_state("networkidle", timeout=20000)
    except Exception as e:
        logger.warning(f"{db_name}: login attempt failed — {e}")


async def _scrape_db(
    page: object,
    name: str,
    db_url: str,
    query: str,
    db_config: DatabaseConfig,
    config: Config,
) -> list[PaperRecord]:
    from playwright.async_api import Page

    assert isinstance(page, Page)

    if name == "Web of Science":
        return await _scrape_wos(page, query, db_config)
    elif name == "Scopus":
        return await _scrape_scopus(page, query, db_config)
    elif name == "IEEE Xplore":
        return await _scrape_ieee(page, query, db_config)
    elif name == "ACM Digital Library":
        return await _scrape_acm(page, query, db_config)
    return []


async def _scrape_wos(
    page: object, query: str, db_config: DatabaseConfig
) -> list[PaperRecord]:
    from playwright.async_api import Page

    assert isinstance(page, Page)
    records: list[PaperRecord] = []
    max_results = db_config.max_results_per_query

    try:
        await page.goto(
            "https://www.webofscience.com/wos/woscc/basic-search", timeout=30000
        )
        await page.wait_for_load_state("networkidle", timeout=20000)
        await asyncio.sleep(3)

        search_input = None
        for sel in (
            'input[name="search-main-box"]',
            'input[placeholder*="search"]',
            'textarea[name="value"]',
            "#search-option",
        ):
            el = await page.query_selector(sel)
            if el:
                search_input = sel
                break

        if not search_input:
            logger.warning("Web of Science: could not find search box")
            return []

        await page.fill(search_input, query)
        await asyncio.sleep(1)

        for btn_sel in (
            'button[data-ta="run-search"]',
            'button[type="submit"]',
            ".search-button",
        ):
            btn = await page.query_selector(btn_sel)
            if btn:
                await btn.click()
                break

        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)

        records = await _extract_wos_results(page, max_results)

    except Exception as e:
        logger.error(f"WoS scraping error: {e}")

    return records


async def _extract_wos_results(page: object, max_results: int) -> list[PaperRecord]:
    from playwright.async_api import Page

    assert isinstance(page, Page)
    records: list[PaperRecord] = []

    try:
        result_items = await page.query_selector_all("app-record, .search-results-item")
        for item in result_items[:max_results]:
            try:
                title_el = await item.query_selector(".title, h3 a, .record-title")
                title = await title_el.inner_text() if title_el else ""
                title = title.strip()
                if not title:
                    continue

                authors_els = await item.query_selector_all(
                    ".authors .value, .author-name"
                )
                authors = [await el.inner_text() for el in authors_els]
                authors = [a.strip() for a in authors if a.strip()]

                year_el = await item.query_selector(".pub-year, .year")
                year_text = await year_el.inner_text() if year_el else ""
                year = _extract_year(year_text)

                venue_el = await item.query_selector(".source-title, .venue")
                venue = await venue_el.inner_text() if venue_el else None
                if venue:
                    venue = venue.strip()

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
    except Exception as e:
        logger.warning(f"WoS result extraction error: {e}")

    return records


async def _scrape_scopus(
    page: object, query: str, db_config: DatabaseConfig
) -> list[PaperRecord]:
    from playwright.async_api import Page

    assert isinstance(page, Page)
    records: list[PaperRecord] = []
    max_results = db_config.max_results_per_query

    try:
        await page.goto(
            "https://www.scopus.com/search/form.uri?display=basic", timeout=30000
        )
        await page.wait_for_load_state("networkidle", timeout=20000)
        await asyncio.sleep(3)

        for sel in (
            "#searchfield",
            'textarea[name="searchterm1"]',
            'input[name="query"]',
        ):
            el = await page.query_selector(sel)
            if el:
                await page.fill(sel, query)
                break

        for btn_sel in (
            'button[data-testid="submit-search"]',
            'button[type="submit"]',
            "#searchBtn",
        ):
            btn = await page.query_selector(btn_sel)
            if btn:
                await btn.click()
                break

        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)

        result_items = await page.query_selector_all(
            'article[data-testid="result-item"], .searchArea .resultRow'
        )

        for item in result_items[:max_results]:
            try:
                title_el = await item.query_selector("h3 a, .documentTitle a")
                title = await title_el.inner_text() if title_el else ""
                title = title.strip()
                if not title:
                    continue

                authors_el = await item.query_selector(".authorNames, .authors")
                authors_text = await authors_el.inner_text() if authors_el else ""
                authors = [a.strip() for a in authors_text.split(",") if a.strip()]

                year_text = ""
                for year_sel in (".year", "span[data-testid='year']"):
                    el = await item.query_selector(year_sel)
                    if el:
                        year_text = await el.inner_text()
                        break
                year = _extract_year(year_text)

                venue_el = await item.query_selector(".sourceTitle, .publicationName")
                venue = await venue_el.inner_text() if venue_el else None
                if venue:
                    venue = venue.strip()

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

    except Exception as e:
        logger.error(f"Scopus scraping error: {e}")

    return records


async def _scrape_ieee(
    page: object, query: str, db_config: DatabaseConfig
) -> list[PaperRecord]:
    from playwright.async_api import Page

    assert isinstance(page, Page)
    records: list[PaperRecord] = []
    max_results = db_config.max_results_per_query

    try:
        search_url = (
            f"https://ieeexplore.ieee.org/search/searchresult.jsp?queryText={query}"
        )
        await page.goto(search_url, timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=20000)
        await asyncio.sleep(3)

        result_items = await page.query_selector_all(
            ".List-results-items, .result-item"
        )
        for item in result_items[:max_results]:
            try:
                title_el = await item.query_selector("h2 a, .result-item-title a")
                title = await title_el.inner_text() if title_el else ""
                title = title.strip()
                if not title:
                    continue

                authors_el = await item.query_selector(".authors-info, .author")
                authors_text = await authors_el.inner_text() if authors_el else ""
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
                venue = await venue_el.inner_text() if venue_el else None
                if venue:
                    venue = venue.strip()

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

    except Exception as e:
        logger.error(f"IEEE Xplore scraping error: {e}")

    return records


async def _scrape_acm(
    page: object, query: str, db_config: DatabaseConfig
) -> list[PaperRecord]:
    from playwright.async_api import Page

    assert isinstance(page, Page)
    records: list[PaperRecord] = []
    max_results = db_config.max_results_per_query

    try:
        await page.goto("https://dl.acm.org/search/", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=20000)
        await asyncio.sleep(3)

        for sel in ("#search-input", 'input[name="AllField"]', 'input[type="search"]'):
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
                title = await title_el.inner_text() if title_el else ""
                title = title.strip()
                if not title:
                    continue

                authors_els = await item.query_selector_all(".hlFld-ContribAuthor")
                authors = [await el.inner_text() for el in authors_els]
                authors = [a.strip() for a in authors if a.strip()]

                year_text = ""
                date_el = await item.query_selector(".bookPubDate, .issue-item__detail")
                if date_el:
                    year_text = await date_el.inner_text()
                year = _extract_year(year_text)

                venue_el = await item.query_selector(".issue-item__detail em")
                venue = await venue_el.inner_text() if venue_el else None

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
                        venue=str(venue).strip() if venue else None,
                        doi=doi,
                        source_database="ACM Digital Library",
                        retrieved_at=datetime.datetime.utcnow().isoformat(),
                    )
                )
            except Exception:
                continue

    except Exception as e:
        logger.error(f"ACM DL scraping error: {e}")

    return records


def _extract_year(text: str) -> int | None:
    m = re.search(r"\b(19|20)\d{2}\b", str(text))
    if m:
        try:
            return int(m.group(0))
        except ValueError:
            pass
    return None
