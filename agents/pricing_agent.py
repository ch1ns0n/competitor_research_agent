import os
import uvicorn
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from infra.embedding import embed_text
from memory_bank.pricing_memory import PricingMemory
from scrapers.logger import get_logger


API_KEY = os.getenv("A2A_API_KEY", "secret")
app = FastAPI(title="Pricing Agent")

logger = get_logger("pricing_agent")


# ------------------------------------------------------------
# INPUT MODEL
# ------------------------------------------------------------

class PricingReq(BaseModel):
    product: Dict[str, Any]
    reviews: List[Dict[str, Any]]


# ------------------------------------------------------------
# BUSINESS LOGIC
# ------------------------------------------------------------

def compute_recommended_price(
    base_price: float,
    competitor_prices: List[float],
    positive_ratio: float
) -> Dict[str, Any]:
    import numpy as np

    if not competitor_prices:
        return {
            "recommended_price": round(base_price, 2),
            "competitor_average_price": None,
            "sentiment_score": positive_ratio,
            "business_reason": [
                "No competitor pricing available – keeping current price."
            ]
        }

    competitor_avg = float(np.mean(competitor_prices))

    # ==============================
    # 1️⃣ SENTIMENT FACTOR
    # ==============================
    if positive_ratio >= 0.85:
        sentiment_factor = 0.12        # naik lebih berani
    elif positive_ratio >= 0.70:
        sentiment_factor = 0.05        # naik ringan
    else:
        sentiment_factor = -0.03       # turunkan sedikit

    # ==============================
    # 2️⃣ GAP MARKET
    # ==============================
    gap = competitor_avg - base_price

    # maksimum 40% dari gap kompetitor
    competitor_adjust = gap * 0.40

    # ==============================
    # 3️⃣ HITUNG HARGA BARU
    # ==============================
    new_price = base_price + competitor_adjust + (base_price * sentiment_factor)

    # ==============================
    # 4️⃣ HARD LIMITS
    # supaya tidak kelewat ekstrem
    # ==============================
    min_allowed = base_price * 0.85   # tidak turun > 15%
    max_allowed = base_price * 1.20   # tidak naik > 20%

    new_price = max(min(new_price, max_allowed), min_allowed)

    # ==============================
    # 5️⃣ BUSINESS NARRATION
    # ==============================
    reasons = []

    if positive_ratio < 0.65:
        reasons.append("Customer sentiment is weak – apply conservative pricing.")

    elif gap > 0 and positive_ratio > 0.75:
        reasons.append("Product underpriced vs competitors, and sentiment strong – price increase is justified.")

    elif gap > 0:
        reasons.append("Competitors priced higher – slight upward correction suggested.")

    else:
        reasons.append("Competitors are cheaper – maintaining price is recommended.")

    return {
        "recommended_price": round(new_price, 2),
        "competitor_average_price": round(competitor_avg, 2),
        "sentiment_score": round(positive_ratio, 2),
        "business_reason": reasons
    }



# ------------------------------------------------------------
# MAIN ENDPOINT
# ------------------------------------------------------------

@app.post("/a2a/execute")
def pricing_api(req: Dict[str, Any], x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if req.get("task") != "recommend_price":
        return {"status": "error", "msg": "Unknown task"}

    payload = req.get("input", {})
    product = payload.get("product", {})
    reviews = payload.get("reviews", [])

    pid = product.get("product_id")
    if not pid:
        raise HTTPException(status_code=400, detail="Missing product_id")

    pricing_mem = PricingMemory()

    # Extract competitor prices from memory
    competitor_prices = []
    try:
        # Use product title embedding for similarity
        title = product.get("title", "") or product.get("product_id")
        q_emb = embed_text(title)

        search_results = pricing_mem.search(q_emb, top_k=10)

        for r in search_results:
            meta = r["record"]["metadata"]
            cp = meta.get("base_price") or meta.get("recommended_price")
            if cp:
                competitor_prices.append(cp)

    except Exception as e:
        logger.exception(f"[ERROR] Failed loading competitor memory: {e}")

    # Extract positive ratio from sentiment agent (or baseline)
    # If sentiment not present, assume neutral 50%
    positive_ratio = 0.50
    for r in reviews:
        # If review has rating, approximate 4/5 or 5/5 as positive
        score = r.get("rating")
        if score is not None:
            positive_ratio = max(0.1, min(0.9, score / 5))

    # Base price – if missing, fallback
    base_price = product.get("price") or product.get("base_price") or 100.0

    result = compute_recommended_price(
        base_price=base_price,
        competitor_prices=competitor_prices,
        positive_ratio=positive_ratio
    )

    # Save memory back to FAISS
    try:
        emb = embed_text(f"{result['recommended_price']} ratio={positive_ratio}")
        pricing_mem.save(
            pid,
            {"recommended_price": result["recommended_price"],
             "base_price": base_price,
             "positive_ratio": positive_ratio},
            embedding=emb
        )
    except Exception as e:
        logger.exception(f"[ERROR] Failed saving pricing memory: {e}")

    return {"status": "ok", "result": result}


# ------------------------------------------------------------
# AGENT CARD
# ------------------------------------------------------------

@app.get("/.well-known/agent-card.json")
def agent_card():
    base = os.getenv("PRICING_AGENT_URL", "http://localhost:8003")
    return {
        "name": "pricing_agent",
        "version": "0.3.0",
        "description": "Competitive AI pricing model agent",
        "capabilities": ["recommend_price"],
        "url": base
    }


# ------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)