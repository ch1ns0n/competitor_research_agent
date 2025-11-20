from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from memory_bank.pricing_memory import PricingMemory
import uvicorn, os

API_KEY = os.getenv("A2A_API_KEY", "secret")
app = FastAPI(title="Pricing Agent (A2A)")

class A2AReq(BaseModel):
    task: str
    input: dict

@app.post("/a2a/execute")
def a2a_execute(req: A2AReq, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if req.task == "recommend_price":
        product = req.input.get("product",{})
        reviews = req.input.get("reviews",[])
        base_price = product.get("base_price") or 1000.0

        pos_ratio = (
            sum(1 for r in reviews if r.get("rating",0)>=4) / max(1,len(reviews))
            if reviews else 0.5
        )

        if pos_ratio > 0.75:
            factor = 1.03
        elif pos_ratio < 0.4:
            factor = 0.96
        else:
            factor = 1.0

        recommended = round(base_price * factor,2)

        result = {
            "recommended_price": recommended,
            "base_price": base_price,
            "positive_ratio": pos_ratio
        }

        # --- NEW: simpan ke memory ---
        pm = PricingMemory()
        pm.add({
            "product_id": product.get("product_id"),
            "recommended_price": recommended,
            "base_price": base_price,
            "positive_ratio": pos_ratio
        })

        return {"status":"ok","result": result}

    return {"status":"error","msg":"unknown task"}

@app.get("/.well-known/agent-card.json")
def card():
    base = os.getenv("AGENT_BASE_URL","http://localhost:8003")
    return {
        "name":"pricing_agent",
        "version":"0.1.0",
        "description":"Pricing Agent",
        "capabilities":["recommend_price"],
        "url": base,
        "securitySchemes": {"x-api-key":{"type":"apiKey"}}
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)