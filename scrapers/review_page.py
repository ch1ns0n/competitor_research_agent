from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from scrapers.util import smart_get, is_blocked_html
import time

def parse_reviews_from_html(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[Dict[str, Any]] = []
    # Amazon reviews are in div[data-hook='review']
    for review in soup.select("div[data-hook='review']"):
        body_el = review.select_one("span[data-hook='review-body']")
        # rating element can be i[data-hook='review-star-rating'] span or span.a-icon-alt
        rating_el = review.select_one("i[data-hook='review-star-rating'] span") or review.select_one("span.a-icon-alt")
        text = body_el.get_text(strip=True) if body_el else ""
        rating = None
        if rating_el:
            try:
                rating = float(rating_el.get_text(strip=True).split()[0])
            except:
                rating = None
        out.append({"text": text, "rating": rating})
    return out

def scrape_product_reviews(product_id: str, page: int = 1, proxies: Optional[dict] = None, playwright_timeout: int = 30000) -> List[Dict[str, Any]]:
    """
    Scrape review page for given product_id (ASIN). Try requests first, fallback to Playwright.
    """
    url = f"https://www.amazon.com/product-reviews/{product_id}/?pageNumber={page}"
    try:
        resp = smart_get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept-Language": "en-US,en;q=0.9",
                },
            proxies=proxies
            )
        if is_blocked_html(resp.text) or not resp.text:
            raise RuntimeError("blocked or empty")
        return parse_reviews_from_html(resp.text)
    except Exception:
        # fallback Playwright
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            raise RuntimeError("Playwright not installed. pip install playwright and run `playwright install`") from e

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=playwright_timeout)
            html = page.content()
            browser.close()
            return parse_reviews_from_html(html)