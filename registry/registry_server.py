from fastapi import FastAPI
import uvicorn
import json
import os

app = Fastapi = FastAPI(title="Agent Registry (MVP)")

# load agent cards from files in ./registry/cards/
BASE = os.path.dirname(__file__)
CARDS_DIR = os.path.join(BASE, "cards")

@app.get("/agents")
def list_agents():
    cards = []
    for fn in os.listdir(CARDS_DIR):
        if fn.endswith(".json"):
            with open(os.path.join(CARDS_DIR, fn)) as f:
                cards.append(json.load(f))
    return {"agents": cards}

@app.get("/agents/{name}")
def get_agent(name: str):
    path = os.path.join(CARDS_DIR, f"{name}.json")
    if not os.path.exists(path):
        return {"error":"not found"}, 404
    with open(path) as f:
        return json.load(f)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)