from fastapi import FastAPI
import uvicorn

app = FastAPI()

# change ports to match where your agents run
AGENTS = {
    "scraper_agent": {"agent_url": "http://localhost:8001"},
    "sentiment_agent": {"agent_url": "http://localhost:8002"},
    "pricing_agent": {"agent_url": "http://localhost:8003"}
}

@app.get("/agents/{name}")
def get_agent(name: str):
    return AGENTS.get(name, {})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)