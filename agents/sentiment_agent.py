from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from memory_bank.sentiment_memory import SentimentMemory
from infra.embedding import embed_text
import numpy as np
import uvicorn, os, json

API_KEY = os.getenv("A2A_API_KEY", "secret")
app = FastAPI(title="Sentiment Agent (A2A)")

class A2AReq(BaseModel):
    task: str
    input: dict

# Static embedder + toy model
embedder = SentenceTransformer("all-MiniLM-L6-v2")
X = embedder.encode(["good","excellent","bad","terrible"])
y = [1,1,0,0]
clf = LogisticRegression()
clf.fit(X,y)

@app.post("/a2a/execute")
def a2a_execute(req: A2AReq, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if req.task == "analyze_reviews":
        reviews = req.input.get("reviews", [])
        texts = [r.get("text","") for r in reviews]
        product_id = req.input.get("product_id")

        if not texts:
            result = {
                "n_reviews": 0,
                "positive_ratio": 0.0,
                "top_issues": []
            }

            sm = SentimentMemory()
            sm.save(
                key=product_id,
                metadata=result
            )

            return {"status":"ok","result": result}

        embs = embedder.encode(texts)
        preds = clf.predict(embs)
        pos_ratio = float(preds.mean())
        
        issues = []
        for t in texts:
            if "ship" in t.lower():
                issues.append("shipping")

        result = {
            "n_reviews": len(texts),
            "positive_ratio": pos_ratio,
            "top_issues": list(set(issues))
        }

        # SAVE TO VECTOR MEMORY (FAISS)
        sm = SentimentMemory()
        vector = embed_text("\n".join(texts))
        sm.save(
            key=product_id,
            metadata=result,
            embedding=vector
        )

        return {"status":"ok","result": result}

    return {"status":"error","msg":"unknown task"}

@app.get("/.well-known/agent-card.json")
def card():
    base = os.getenv("AGENT_BASE_URL","http://localhost:8002")
    return {
        "name": "sentiment_agent",
        "version": "0.1.0",
        "description": "Sentiment Agent",
        "capabilities": ["analyze_reviews"],
        "url": base,
        "securitySchemes": {"x-api-key":{"type":"apiKey"}}
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
