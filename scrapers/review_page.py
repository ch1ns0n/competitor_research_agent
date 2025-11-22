from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from scrapers.util import smart_get, is_blocked_html
import time


def parse_reviews_from_html(html: str) -> List[Dict[str, Any]]:
    """
    Parse raw HTML of an Amazon review page and extract:
    - review text
    - rating
    """
    soup = BeautifulSoup(html, "html.parser")
    out: List[Dict[str, Any]] = []

    review_elems = soup.select("div[data-hook='review']")
    for r in review_elems:
        body_el = r.select_one("span[data-hook='review-body']")
        rating_el = (
            r.select_one("i[data-hook='review-star-rating'] span")
            or r.select_one("span.a-icon-alt")
        )

        text = body_el.get_text(strip=True) if body_el else ""
        rating = None

        if rating_el:
            try:
                rating = float(rating_el.get_text(strip=True).split()[0])
            except:
                rating = None

        out.append({
            "text": text,
            "rating": rating
        })

    return out


def scrape_reviews_with_playwright(url: str, playwright_timeout: int = 30000):
    """
    Fallback scraper that opens Amazon using Playwright
    in headless mode to bypass robot detection.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        raise RuntimeError(
            "Playwright not installed. Run:\n"
            "pip install playwright\n"
            "playwright install chromium"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=playwright_timeout)
        html = page.content()
        browser.close()

        return parse_reviews_from_html(html)


def scrape_product_reviews(
    product_id: str,
    max_pages: int = 5,
    proxies: Optional[dict] = None,
    playwright_timeout: int = 30000,
) -> List[Dict[str, Any]]:
    """
    Scrape multiple Amazon review pages for a product.
    
    Strategy:
    1. Try normal requests first
    2. If blocked (captcha/login redirect), fallback to Playwright
    3. Stop if a page has zero reviews
    """
    all_reviews = []

    for page_number in range(1, max_pages + 1):
        url = f"https://www.amazon.com/product-reviews/{product_id}/?pageNumber={page_number}"

        try:
            resp = smart_get(url, proxies=proxies)
            html = resp.text

            blocked = (
                is_blocked_html(html)
                or "signin" in resp.url.lower()
                or "captcha" in html.lower()
            )

            if blocked:
                print(f"[!] Page {page_number} blocked → using Playwright…")
                page_reviews = scrape_reviews_with_playwright(url, playwright_timeout)
            else:
                page_reviews = parse_reviews_from_html(html)

        except Exception as e:
            print(f"[!] Requests failed ({e}) → using Playwright")
            page_reviews = scrape_reviews_with_playwright(url, playwright_timeout)

        if not page_reviews:
            print(f"[!] No more reviews on page {page_number}, stopping.")
            break

        all_reviews.extend(page_reviews)
        time.sleep(1)

    return all_reviews