from fastapi import FastAPI, Request, Header, HTTPException
from pydantic import BaseModel
from memory_bank.product_memory import ProductMemory
import uvicorn, time, random
import json, os

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

# MCP endpoints (same as before)
@app.post("/fetch_product_page")
def fetch_product_page(req: FetchProductReq):
    pid = "mock-" + req.url.rstrip("/").split("/")[-1]
    mock = {
        "product_id": pid,
        "title": "Mock Product " + pid,
        "specs": {"gpu": "RTX 4090", "ram": "16GB"},
        "marketplace": "mock_market",
        "url": req.url,
        "base_price": 1999.0 + random.choice([-50,0,50])
    }
    
    pm = ProductMemory()
    pm.add(mock)
    
    return {"status":"ok","product": mock}

@app.post("/fetch_reviews")
def fetch_reviews(req: FetchReviewsReq):
    reviews = [
        {"id": f"r{req.product_id}_1", "text":"Great GPU, runs cool.", "rating":5},
        {"id": f"r{req.product_id}_2", "text":"Expensive but worth it", "rating":4},
        {"id": f"r{req.product_id}_3", "text":"Shipping slow, packaging damaged", "rating":2},
        {"id": f"r{req.product_id}_4", "text":"Driver issues sometimes", "rating":3}
    ]
    return {"status":"ok","reviews": reviews}

# A2A execute endpoint
@app.post("/a2a/execute")
async def a2a_execute(req: A2AReq, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    # Support tasks: 'fetch_product_page' or 'fetch_reviews'
    if req.task == "fetch_product_page":
        url = req.input.get("url")
        return fetch_product_page(FetchProductReq(url=url))
    if req.task == "fetch_reviews":
        pid = req.input.get("product_id")
        page = req.input.get("page",1)
        return fetch_reviews(FetchReviewsReq(product_id=pid, page=page))
    return {"status":"error","msg":"unknown task"}

@app.get("/.well-known/agent-card.json")
def agent_card():
    # serve AgentCard describing this agent
    base = os.getenv("AGENT_BASE_URL","http://localhost:8001")
    card = {
        "name": "scraper_agent",
        "version": "0.1.0",
        "description": "Scraper Agent exposing MCP & A2A endpoints",
        "capabilities": ["fetch_product_page","fetch_reviews"],
        "url": base,
        "securitySchemes": {"x-api-key":{"type":"apiKey"}}
    }
    return card

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)