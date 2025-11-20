from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import time
import random

app = FastAPI(title="Mock MCP Server - Product Tools")

class FetchProductReq(BaseModel):
    url: str

class FetchReviewsReq(BaseModel):
    product_id: str
    page: int = 1

@app.post("/fetch_product_page")
def fetch_product_page(req: FetchProductReq):
    # Mock structured product
    pid = "mock-" + req.url.rstrip("/").split("/")[-1]
    mock = {
        "product_id": pid,
        "title": "Mock Product " + pid,
        "specs": {"gpu": "RTX 4090", "ram": "16GB"},
        "marketplace": "mock_market",
        "url": req.url,
        # base_price is optional; used by pricing agent
        "base_price": 1999.0 + random.choice([-50,0,50])
    }
    return {"status":"ok","product": mock}

@app.post("/fetch_reviews")
def fetch_reviews(req: FetchReviewsReq):
    # return mocked sample reviews (diverse ratings)
    reviews = [
        {"id": f"r{req.product_id}_1", "text":"Great GPU, runs cool.", "rating":5},
        {"id": f"r{req.product_id}_2", "text":"Expensive but worth it", "rating":4},
        {"id": f"r{req.product_id}_3", "text":"Shipping slow, packaging damaged", "rating":2},
        {"id": f"r{req.product_id}_4", "text":"Driver issues sometimes", "rating":3}
    ]
    return {"status":"ok","reviews": reviews}

@app.get("/health")
def health():
    return {"status":"ok","time": time.time()}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)