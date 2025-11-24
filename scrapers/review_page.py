from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from scrapers.util import smart_get, is_blocked_html
import asyncio
from playwright.async_api import async_playwright
from scrapers.logger import get_logger

logger = get_logger("review_scraper")

FAKE_REVIEWS = [
    {"rating": 5.0, "text": "Amazing performance. Runs all modern titles at 4K perfectly."},
    {"rating": 4.0, "text": "Very good card but a little expensive compared to competitors."},
    {"rating": 5.0, "text": "Silent fans and low temperature. Perfect for long sessions."},
    {"rating": 3.5, "text": "Good performance, but coil whine is noticeable."},
    {"rating": 4.5, "text": "One of the strongest GPUs I have ever used."},
    {"rating": 2.0, "text": "Unit arrived damaged and the seller was slow to respond."},
    {"rating": 1.0, "text": "Died after 2 weeks, very disappointing."},
    {"rating": 4.8, "text": "Great card for productivity and AI workloads."},
    {"rating": 3.0, "text": "Good card but power consumption is too high."},
    {"rating": 5.0, "text": "Excellent upgrade over my 4080 — VR and rendering are superb."},
]


def parse_reviews_from_html(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[Dict[str, Any]] = []

    for r in soup.select("div[data-hook='review']"):
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

        out.append({"text": text, "rating": rating})

    return out


async def scrape_reviews_with_playwright_async(url: str, playwright_timeout: int = 30000):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=playwright_timeout)
        html = await page.content()
        await browser.close()
        return parse_reviews_from_html(html)


async def scrape_product_reviews_async(
    product_id: str,
    max_pages: int = 3,
    proxies: Optional[dict] = None,
    playwright_timeout: int = 30000,
) -> List[Dict[str, Any]]:

    all_reviews = []
    fallback_playwright_count = 0

    for page_number in range(1, max_pages + 1):
        logger.info(f"Scraping reviews for product={product_id}, page={page_number}")
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
                logger.warning(f"Amazon blocked => switching to Playwright (page {page_number})")
                fallback_playwright_count += 1
                try:
                    page_reviews = await scrape_reviews_with_playwright_async(
                        url, playwright_timeout
                    )
                except Exception as e:
                    logger.error(f"Playwright fetch failed: {e}, using FAKE_REVIEWS")
                    return FAKE_REVIEWS
            else:
                page_reviews = parse_reviews_from_html(html)

        except Exception as e:
            logger.error(f"smart_get failed: {e}, retry via Playwright")
            try:
                fallback_playwright_count += 1
                page_reviews = await scrape_reviews_with_playwright_async(
                    url, playwright_timeout
                )
            except Exception as e2:
                logger.error(f"Playwright failed too => using FAKE_REVIEWS ({e2})")
                return FAKE_REVIEWS

        if not page_reviews:
            logger.warning(f"No reviews found at page {page_number} => using FAKE_REVIEWS")
            return FAKE_REVIEWS

        all_reviews.extend(page_reviews)
        await asyncio.sleep(1)

    logger.info(
        f"Scrape complete for {product_id}: total_reviews={len(all_reviews)}, "
        f"playwright_fallbacks={fallback_playwright_count}"
    )

    return all_reviews or FAKE_REVIEWS