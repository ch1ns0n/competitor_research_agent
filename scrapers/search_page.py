from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from scrapers.util import smart_get, is_blocked_html, extract_asin_from_url
import re

def _parse_search_html(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    asins = set()

    # Amazon search results use <div data-asin="...">
    for item in soup.select("div[data-asin]"):
        asin = item.get("data-asin")
        if asin and len(asin) == 10:
            asins.add(asin)

    # fallback – also search links like /dp/ASIN
    if len(asins) < 5:
        for a in soup.find_all("a", href=True):
            asin = extract_asin_from_url(a["href"])
            if asin:
                asins.add(asin)

    return list(asins)

def scrape_search_results(
        query: str,
        page: int = 1,
        proxies: Optional[dict] = None,
        playwright_timeout: int = 30000
) -> List[str]:
    """
    Scrape Amazon search page for given query. Returns list of ASINs.
    """
    # Example query: https://www.amazon.com/s?k=rtx+4090&page=2
    q = query.replace(" ", "+")
    url = f"https://www.amazon.com/s?k={q}&page={page}"

    try:
        resp = smart_get(url, proxies=proxies)
        if is_blocked_html(resp.text):
            raise RuntimeError("blocked/empty")
        return _parse_search_html(resp.text)

    except Exception:
        # fallback Playwright
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            raise RuntimeError(
                "Playwright not installed. Run: pip install playwright && playwright install"
            ) from e

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page_ctx = browser.new_page()
            page_ctx.goto(url, timeout=playwright_timeout)
            html = page_ctx.content()
            browser.close()
            return _parse_search_html(html)