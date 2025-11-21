import uvicorn, os, json
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from memory_bank.product_memory import ProductMemory
from infra.embedding import embed_text
from scrapers.product_page import scrape_product_page
from scrapers.review_page import scrape_product_reviews
from scrapers.search_page import scrape_search_results

API_KEY = os.getenv("A2A_API_KEY", "secret")
app = FastAPI(title="Scraper Agent (A2A + MCP)")

class A2AReq(BaseModel):
    task: str
    input: dict

class FetchProductReq(BaseModel):
    url: str

class FetchReviewsReq(BaseModel):
    product_id: str
    page: int = 1

def handle_real_amazon_scrape(url: str):
    """Scrape Amazon product page and persist to vector memory."""
    # 1. scrape
    data = scrape_product_page(url)
    product = {
        "product_id": data.get("product_id"),
        "title": data.get("title"),
        "price": data.get("price"),
        "rating": data.get("rating"),
        "rating_raw": data.get("rating_raw"),
        "marketplace": "amazon",
        "url": url
        }
    
    # 2. Store in vector memory
    pm = ProductMemory()
    vector = embed_text(json.dumps(product, ensure_ascii=False))
    pm.save(
        key=product["product_id"],
        metadata=product,
        embedding=vector
        )
    
    return product


def handle_mock_scrape(url: str):
    """Fallback old mock behavior for non-Amazon targets."""
    import random
    
    pid = "mock-" + url.rstrip("/").split("/")[-1]
    mock = {
        "product_id": pid,
        "title": "Mock Product " + pid,
        "specs": {"gpu": "RTX 4090", "ram": "16GB"},
        "marketplace": "mock_market",
        "url": url,
        "base_price": 1999.0 + random.choice([-50, 0, 50])
        }
    
    pm = ProductMemory()
    vector = embed_text(json.dumps(mock, ensure_ascii=False))
    pm.save(
        key=mock["product_id"],
        metadata=mock,
        embedding=vector
        )
    
    return mock


@app.post("/fetch_product_page")
def fetch_product_page(req: FetchProductReq):
    url = req.url.lower()
    
    if "amazon." in url:
        product = handle_real_amazon_scrape(req.url)
        return {"status": "ok", "product": product}
    
    # fallback to mock for anything else
    product = handle_mock_scrape(req.url)
    return {"status": "ok", "product": product}


@app.post("/fetch_reviews")
def fetch_reviews(req: FetchReviewsReq):
    """Amazon or mock review fetcher."""
    pid = req.product_id
    
    # Amazon review scrape
    if pid and not pid.startswith("mock"):
        reviews = scrape_product_reviews(pid, page=req.page)
        # expected return list of dicts with "text" and "rating"
        return {"status": "ok", "reviews": reviews}
    
    # Mock fallback
    reviews = [
        {"id": f"r{pid}_1", "text": "Great GPU, runs cool.", "rating": 5},
        {"id": f"r{pid}_2", "text": "Expensive but worth it", "rating": 4},
        {"id": f"r{pid}_3", "text": "Shipping slow, packaging damaged", "rating": 2},
        {"id": f"r{pid}_4", "text": "Driver issues sometimes", "rating": 3}
        ]
    return {"status": "ok", "reviews": reviews}


@app.post("/a2a/execute")
async def a2a_execute(req: A2AReq, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if req.task == "fetch_product_page":
        url = req.input.get("url")
        return fetch_product_page(FetchProductReq(url=url))

    if req.task == "fetch_reviews":
        pid = req.input.get("product_id")
        page = req.input.get("page", 1)
        return fetch_reviews(FetchReviewsReq(product_id=pid, page=page))

    # NEW TASK
    if req.task == "search_products":
        query = req.input.get("query")
        page = req.input.get("page", 1)
        asins = scrape_search_results(query, page=page)
        return {"status": "ok", "asins": asins}

    return {"status": "error", "msg": "unknown task"}


@app.get("/.well-known/agent-card.json")
def agent_card():
    base = os.getenv("AGENT_BASE_URL", "http://localhost:8001")
    card = {
        "name": "scraper_agent",
        "version": "0.2.0",
        "description": "Hybrid Scraper Agent for Amazon + Mock",
        "capabilities": ["fetch_product_page", "fetch_reviews", "search_products"],
        "url": base,
        "securitySchemes": {"x-api-key": {"type": "apiKey"}}
        }
    return card


# if name == "main":
#     uvicorn.run(app, host="0.0.0.0", port=8001)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)