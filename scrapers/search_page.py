import asyncio
import urllib.parse
from typing import List, Optional
from bs4 import BeautifulSoup

from scrapers.util import smart_get, is_blocked_html
from scrapers.logger import get_logger
from playwright.async_api import async_playwright

logger = get_logger("search_scraper")


def parse_search_html(html: str) -> List[str]:
    """Extract ASINs from Amazon search result HTML."""
    soup = BeautifulSoup(html, "html.parser")
    asins = []

    for item in soup.select("div[data-asin]"):
        asin = item.get("data-asin", "").strip()
        if len(asin) == 10:
            asins.append(asin)

    return list(dict.fromkeys(asins))  # dedupe


async def scrape_search_playwright(url: str, timeout: int = 30000) -> List[str]:
    """Render search page using Playwright async."""
    logger.info(f"[PLAYWRIGHT] Launching headless browser for {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=timeout)
        html = await page.content()
        await browser.close()

    asins = parse_search_html(html)
    logger.info(f"[PLAYWRIGHT] Extracted {len(asins)} ASINs")

    return asins


async def scrape_search_results(
    query: str,
    page: int = 1,
    proxies: Optional[dict] = None,
) -> List[str]:
    """
    Amazon search scraper with fallback:
    1. requests → BS4
    2. If blocked → Playwright async
    """

    encoded = urllib.parse.quote_plus(query)
    url = f"https://www.amazon.com/s?k={encoded}&page={page}"

    logger.info(f"[SCRAPE] Searching Amazon for '{query}', page={page}")

    # -----------------------------------
    # Attempt normal HTTP request first
    # -----------------------------------
    try:
        resp = smart_get(url, proxies=proxies)
        html = resp.text

        if is_blocked_html(html):
            logger.warning("[SCRAPE] Blocked by Amazon – switching to Playwright")
            raise RuntimeError("blocked")

        asins = parse_search_html(html)
        logger.info(f"[SCRAPE] Found {len(asins)} ASINs via requests")
        return asins

    except Exception as e:
        logger.warning(f"[SCRAPE] HTTP fetch failed: {e}")

    # -----------------------------------
    # Fallback → Playwright async
    # -----------------------------------
    try:
        return await scrape_search_playwright(url)
    except Exception as e:
        logger.error(f"[SCRAPE] Playwright also failed: {e}")
        return []