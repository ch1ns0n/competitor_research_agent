import os
import requests
import json

from memory_bank.product_memory import ProductMemory
from memory_bank.sentiment_memory import SentimentMemory
from memory_bank.pricing_memory import PricingMemory


API_KEY = os.getenv("A2A_API_KEY", "secret")

class RemoteCoordinator:

    def __init__(self):
        self.product_mem = ProductMemory()
        self.sentiment_mem = SentimentMemory()
        self.pricing_mem = PricingMemory()

    def discover(self, agent_name):
        # In production this hits the registry.
        r = requests.get(f"http://localhost:9000/agents/{agent_name}")
        r.raise_for_status()
        return r.json()

    def call_agent(self, card, task, payload):
        base_url = card["agent_url"]
        exec_url = base_url.rstrip("/") + "/a2a/execute"
        r = requests.post(
            exec_url,
            json={"task": task, "input": payload},
            headers={"X-API-KEY": API_KEY}
        )
        r.raise_for_status()
        return r.json()

    def run(self, product_id: str):
        url = f"https://mocksite.com/product/{product_id}"

        # --------- SCRAPER ---------
        scraper_card = self.discover("scraper_agent")
        product_resp = self.call_agent(scraper_card, "fetch_product_page", {"url": url})
        product = product_resp["product"]

        reviews_resp = self.call_agent(scraper_card, "fetch_reviews", {"product_id": product_id})
        reviews = reviews_resp.get("reviews", [])

        # Save memory
        self.product_mem.save(product_id, product)

        # --------- SENTIMENT ---------
        sentiment_card = self.discover("sentiment_agent")
        sentiment_resp = self.call_agent(sentiment_card, "analyze_reviews", {"reviews": reviews})
        sentiment = sentiment_resp.get("result", {})

        self.sentiment_mem.save(product_id, sentiment)

        # --------- PRICING ---------
        pricing_card = self.discover("pricing_agent")
        pricing_resp = self.call_agent(
            pricing_card,
            "recommend_price",
            {"product": product, "reviews": reviews}
        )
        pricing = pricing_resp.get("result", {})

        self.pricing_mem.save(product_id, pricing)

        # --------- MEMORY LOOKUP ---------
        similar_products = self.product_mem.search(product_id, top_k=5)
        past_sentiments = self.sentiment_mem.search(product_id, top_k=5)
        past_pricing = self.pricing_mem.search(product_id, top_k=5)

        return {
            "product": product,
            "sentiment": sentiment,
            "pricing": pricing,
            "similar_products": similar_products,
            "sentiment_history": past_sentiments,
            "pricing_history": past_pricing
        }


if __name__ == "__main__":
    co = RemoteCoordinator()
    res = co.run("rtx-4090-xyz")
    print(json.dumps(res, indent=2))