"""
Simple in-memory Agent Registry for demonstration.
AgentCards stored here for discovery; production should use persistent registry.
"""
AGENT_CARDS = {}

def register_agent(card: dict):
    AGENT_CARDS[card["name"]] = card
    return True

def get_agent(name: str):
    return AGENT_CARDS.get(name)

def list_agents():
    return list(AGENT_CARDS.keys())

# Example: register mock scraper on import (optional)
if __name__ == "__main__":
    card = {
        "name": "scraper_agent",
        "version": "0.1.0",
        "description": "Mock Scraper Agent exposing MCP endpoints",
        "url": "http://localhost:8001",
        "capabilities": ["fetch_product_page", "fetch_reviews"]
    }
    register_agent(card)
    print("Registered agents:", list_agents())