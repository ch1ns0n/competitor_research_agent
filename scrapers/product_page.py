from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
from infra.util import smart_get, is_blocked_html, parse_price, extract_asin_from_url
from scrapers.logger import get_logger
import re

logger = get_logger("product_scraper")

# Used when everything fails (Amazon blocked and Playwright not available)
FAKE_PRODUCT = {
    "product_id": "FAKE123456",
    "title": "Placeholder GPU (Fallback Mode)",
    "price_raw": "$999.00",
    "price": 999.0,
    "rating_raw": "4.3 out of 5",
    "rating": 4.3,
    "review_count": "1,234 ratings",
    "url": "local-fallback",
    "raw_html_len": 0,
}


def _parse_with_bs(html: str, url: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    def safe(sel):
        el = soup.select_one(sel)
        return el.get_text(strip=True) if el else None

    # Title
    title = safe("#productTitle") or safe("span#title") or safe("h1 span")

    # Price detection
    price_raw = (
        safe(".a-price .a-offscreen")
        or safe("#priceblock_ourprice")
        or safe("#priceblock_dealprice")
        or safe(".priceToPay .a-offscreen")
    )
    price = parse_price(price_raw)

    # If Amazon blocked → price will be None, provide default placeholder
    if price is None:
        price = 899.0

    # Rating
    rating_raw = safe("span[data-hook='rating-out-of-text']") or safe("span.a-icon-alt")
    rating = None
    if rating_raw:
        m = re.search(r"([0-9]+(\.[0-9]+)?)", rating_raw)
        if m:
            try:
                rating = float(m.group(1))
            except:
                rating = None

    review_count = safe("#acrCustomerReviewText") or safe("span[data-hook='total-review-count']")

    # Extract ASIN
    asin = None
    meta_tag = soup.find("th", string=re.compile(r"ASIN", re.I))
    meta_asin = None

    if meta_tag:
        td = meta_tag.find_next_sibling("td")
        if td:
            meta_asin = td.get_text(strip=True)

    if not meta_asin:
        meta_asin = safe("input#ASIN") or safe("div[data-asin]")

    asin = extract_asin_from_url(url) or (
        meta_asin if isinstance(meta_asin, str) and len(meta_asin) == 10 else None
    )

    return {
        "product_id": asin or f"unknown-{abs(hash(url))}",
        "title": title,
        "price_raw": price_raw,
        "price": price,
        "rating_raw": rating_raw,
        "rating": rating,
        "review_count": review_count,
        "url": url,
        "raw_html_len": len(html),
    }


def needs_playwright(parsed: Dict[str, Any]) -> bool:
    # Heuristics → if missing major elements or HTML too small → likely blocked
    if not parsed.get("title"):
        return True
    if parsed.get("raw_html_len", 0) < 3000:
        return True
    return False


def scrape_product_page(
    url: str,
    proxies: Optional[dict] = None,
    playwright_timeout: int = 30000,
) -> Dict[str, Any]:
    """
    1. Try requests + BS4 first
    2. If blocked → fallback to Playwright
    3. If Playwright fails → FAKE_PRODUCT returned
    """

    logger.info(f"Scraping product page: {url}")

    try:
        resp = smart_get(url, proxies=proxies)
        parsed = _parse_with_bs(resp.text, url)

        if is_blocked_html(resp.text) or needs_playwright(parsed):
            raise RuntimeError("Blocked, switching to Playwright")

        logger.info(f"Scrape success → {parsed.get('product_id')}")
        return parsed

    except Exception:
        logger.warning(f"Switching to Playwright for {url}")

        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            logger.error(f"Playwright not installed → fallback FAKE_PRODUCT ({e})")
            return FAKE_PRODUCT

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=playwright_timeout)
                html = page.content()
                parsed = _parse_with_bs(html, url)
                browser.close()

                logger.info(f"Playwright success → {parsed.get('product_id')}")
                return parsed

        except Exception as e:
            logger.error(f"Playwright request failed → FAKE_PRODUCT ({e})")
            return FAKE_PRODUCT