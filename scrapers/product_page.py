from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
from scrapers.util import smart_get, is_blocked_html, parse_price, extract_asin_from_url
import re

def _parse_with_bs(html: str, url: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    def safe(sel):
        el = soup.select_one(sel)
        return el.get_text(strip=True) if el else None

    # Title
    title = safe("#productTitle") or safe("span#title") or safe("h1 span")

    # Price - try several selectors
    price_raw = safe(".a-price .a-offscreen") or safe("#priceblock_ourprice") or safe("#priceblock_dealprice") or safe(".priceToPay .a-offscreen")
    price = parse_price(price_raw)

    # Rating and review count
    rating_raw = safe("span[data-hook='rating-out-of-text']") or safe("span.a-icon-alt")
    rating = None
    if rating_raw:
        # rating_raw like "4.7 out of 5 stars" or "4.7 out of 5"
        m = re.search(r"([0-9]+(\.[0-9]+)?)", rating_raw)
        if m:
            try:
                rating = float(m.group(1))
            except:
                rating = None

    review_count = safe("#acrCustomerReviewText") or safe("span[data-hook='total-review-count']")

    # Try to find ASIN from page meta or url
    asin = None
    # Check meta tags
    meta_asin = None
    meta_tag = soup.find("th", string=re.compile(r"ASIN", re.I))
    if meta_tag:
        # value likely in sibling td
        td = meta_tag.find_next_sibling("td")
        if td:
            meta_asin = td.get_text(strip=True)
    if not meta_asin:
        # some pages have li with data-asin
        meta_asin = safe("input#ASIN") or safe("div[data-asin]")

    # fallback to url
    asin = extract_asin_from_url(url) or (meta_asin if isinstance(meta_asin, str) and len(meta_asin) == 10 else None)

    return {
        "product_id": asin or f"unknown-{abs(hash(url))}",
        "title": title,
        "price_raw": price_raw,
        "price": price,
        "rating_raw": rating_raw,
        "rating": rating,
        "review_count": review_count,
        "url": url,
        "raw_html_len": len(html)
    }

def needs_playwright(parsed: Dict[str, Any]) -> bool:
    # If missing title or content length small -> likely blocked
    if not parsed.get("title"):
        return True
    if parsed.get("raw_html_len", 0) < 3000:
        return True
    return False

def scrape_product_page(url: str, proxies: Optional[dict] = None, playwright_timeout: int = 30000) -> Dict[str, Any]:
    """
    Try requests+BS4 first. If blocked or key fields missing, fallback to Playwright.
    Returns a dict with product fields.
    """
    try:
        resp = smart_get(url, proxies=proxies)
        parsed = _parse_with_bs(resp.text, url)
        if is_blocked_html(resp.text) or needs_playwright(parsed):
            raise RuntimeError("blocked or needs JS")
        return parsed
    except Exception:
        # fallback to Playwright
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            raise RuntimeError("Playwright not installed. pip install playwright and run `playwright install`") from e

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            # optional: configure proxies via browser.launch or context
            page.goto(url, timeout=playwright_timeout)
            html = page.content()
            parsed = _parse_with_bs(html, url)
            browser.close()
            return parsed