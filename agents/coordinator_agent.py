import os, json, logging, requests
from infra.embedding import embed_text, embed_texts
from memory_bank.product_memory import ProductMemory
from memory_bank.sentiment_memory import SentimentMemory
from memory_bank.pricing_memory import PricingMemory

API_KEY = os.getenv("A2A_API_KEY", "secret")
REGISTRY_URL = os.getenv("AGENT_REGISTRY_URL", "http://localhost:9000")
logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
logger = logging.getLogger("coordinator")

class RemoteCoordinator:
    def __init__(self, registry_url: str = REGISTRY_URL):
        self.registry_url = registry_url
        self.product_mem = ProductMemory()
        self.sentiment_mem = SentimentMemory()
        self.pricing_mem = PricingMemory()

    def discover(self, agent_name: str):
        r = requests.get(f"{self.registry_url}/agents/{agent_name}", timeout=5)
        r.raise_for_status()
        card = r.json()
        # Normalize keys
        base = card.get("agent_url") or card.get("agent_card_url") or card.get("url")
        return {"agent_url": base}

    def call_agent(self, card, task, input_payload):
        base = card.get("agent_url")
        if not base:
            raise RuntimeError("missing agent url")
        exec_url = base.rstrip("/") + "/a2a/execute"
        headers = {"X-API-KEY": API_KEY}
        payload = {"task": task, "input": input_payload}
        r = requests.post(exec_url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def run(self, product_id: str):
        logger.info("Run pipeline for %s", product_id)
        if len(product_id) == 10 and product_id.isalnum():
            url = f"https://www.amazon.com/dp/{product_id}"
        else:
            url = f"https://mocksite.com/product/{product_id}"

        # 1. SCRAPER
        scraper = self.discover("scraper_agent")
        prod_resp = self.call_agent(scraper, "fetch_product_page", {"url": url})
        product = prod_resp.get("product", {})
        rev_resp = self.call_agent(scraper, "fetch_reviews", {"product_id": product.get("product_id")})
        reviews = rev_resp.get("reviews", [])

        # 2. Compute embeddings centrally
        product_text = (product.get("title","") + " " + json.dumps(product.get("specs", {}))).strip()
        product_emb = embed_text(product_text)
        review_texts = [r.get("text","") for r in reviews]
        agg_review_text = " ".join(review_texts) if review_texts else ""
        agg_review_emb = embed_text(agg_review_text) if agg_review_text else None

        # 3. Persist product + aggregated review to memory
        try:
            self.product_mem.save(product.get("product_id"), product, embedding=product_emb)
            if agg_review_emb is not None:
                self.sentiment_mem.save(product.get("product_id"), {"n_reviews": len(review_texts)}, embedding=agg_review_emb)
        except Exception as e:
            logger.exception("persist initial memories failed: %s", e)

        # 4. Sentiment
        sentiment_card = self.discover("sentiment_agent")
        sent_resp = self.call_agent(sentiment_card, "analyze_reviews", {"product_id": product.get("product_id"), "reviews": reviews})
        sentiment = sent_resp.get("result", {})
        sent_summary = f"pos_ratio={sentiment.get('positive_ratio')} issues={','.join(sentiment.get('top_issues',[]))}"
        sent_emb = embed_text(sent_summary)
        try:
            self.sentiment_mem.save(product.get("product_id"), sentiment, embedding=sent_emb)
        except Exception:
            logger.exception("persist sentiment failed")

        # 5. Pricing
        pricing_card = self.discover("pricing_agent")
        price_resp = self.call_agent(pricing_card, "recommend_price", {"product": product, "reviews": reviews})
        pricing = price_resp.get("result", {})
        price_emb = embed_text(f"{pricing.get('recommended_price')} ratio={pricing.get('positive_ratio')}")
        try:
            self.pricing_mem.save(product.get("product_id"), pricing, embedding=price_emb)
        except Exception:
            logger.exception("persist pricing failed")

        # 6. Query memories for context
        try:
            similar_products = self.product_mem.search(product_emb, top_k=5)
            recent_sentiments = self.sentiment_mem.search(sent_emb, top_k=5)
            pricing_history = self.pricing_mem.search(price_emb, top_k=5)
        except Exception as e:
            logger.exception("memory search failed: %s", e)
            similar_products, recent_sentiments, pricing_history = [], [], []

        report = {
            "product": product,
            "reviews_count": len(reviews),
            "sentiment": sentiment,
            "pricing": pricing,
            "memory_insights": {
                "similar_products": similar_products,
                "recent_sentiments": recent_sentiments,
                "pricing_history": pricing_history
            }
        }
        return report
    
    def run_search(self, query: str, page:int = 1):
        # 1. Temukan scraper agent
        scraper = self.discover("scraper_agent")
        
        # 2. Panggil search endpoint
        resp = self.call_agent(
            scraper,
            "search_products",
            {"query": query, "page": page}
        )

        asins = resp.get("asins", [])
        results = []

        # 3. Loop semua ASIN
        for asin in asins:
            print(f"\n⚙️ Running pipeline for -> {asin}")
            out = self.run(asin)
            results.append(out)

        return {
            "query": query,
            "found": len(asins),
            "asins": asins,
            "results": results
        }

if __name__ == "__main__":
    rc = RemoteCoordinator()
    out = rc.run_search("rtx 4090", page=1)
    print(json.dumps(out, indent=2))