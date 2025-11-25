import os
import json
import requests

from infra.embedding import embed_text
from memory_bank.product_memory import ProductMemory
from memory_bank.sentiment_memory import SentimentMemory
from memory_bank.pricing_memory import PricingMemory

from scrapers.logger import get_logger


API_KEY = os.getenv("A2A_API_KEY", "secret")
REGISTRY_URL = os.getenv("AGENT_REGISTRY_URL", "http://localhost:9000")

logger = get_logger("coordinator_agent")


class RemoteCoordinator:
    def __init__(self, registry_url: str = REGISTRY_URL):
        self.registry_url = registry_url

        self.product_mem = ProductMemory()
        self.sentiment_mem = SentimentMemory()
        self.pricing_mem = PricingMemory()

    # ------------------------------------------------------------
    #  Discover agent from registry
    # ------------------------------------------------------------
    def discover(self, agent_name: str):
        logger.info(f"[DISCOVER] Looking up agent `{agent_name}`")

        r = requests.get(f"{self.registry_url}/agents/{agent_name}", timeout=5)
        r.raise_for_status()
        card = r.json()

        base = (
            card.get("agent_url")
            or card.get("agent_card_url")
            or card.get("url")
        )

        logger.info(f"[DISCOVER] Found `{agent_name}` at {base}")
        return {"agent_url": base}

    # ------------------------------------------------------------
    #  Execute task on remote agent
    # ------------------------------------------------------------
    def call_agent(self, card, task: str, input_payload: dict):
        base = card.get("agent_url")
        if not base:
            logger.error(f"[CALL] FAILED task={task} – no agent URL")
            raise RuntimeError("missing agent url")

        exec_url = base.rstrip("/") + "/a2a/execute"
        logger.info(f"[CALL] POST {task} → {exec_url}")

        payload = {"task": task, "input": input_payload}
        headers = {"X-API-KEY": API_KEY}

        response = requests.post(
            exec_url,
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        logger.info(f"[CALL] SUCCESS task={task}")
        return response.json()

    # ------------------------------------------------------------
    #  Full analysis pipeline
    # ------------------------------------------------------------
    def generate_business_report(self, analysis: dict) -> str:
        product = analysis.get("product", {})
        sentiment = analysis.get("sentiment", {})
        pricing = analysis.get("pricing", {})
        memory = analysis.get("memory_insights", {})

        pos_ratio = sentiment.get("positive_ratio")
        issues = sentiment.get("top_issues", [])
        similar = memory.get("similar_products", [])
        competitors_count = len(similar)

        my_price = pricing.get("recommended_price")
        avg_competitor_price = pricing.get("competitor_average_price")

        lines = []

        lines.append(f"📌 PRODUCT ANALYSIS REPORT")
        lines.append(f"Product: {product.get('title')}")
        lines.append(f"Marketplace: {product.get('marketplace')}")
        lines.append(f"Price: ${product.get('price')}")
        lines.append(f"Rating: {product.get('rating')} ⭐")
        lines.append("")

        lines.append(f"📊 Market Sentiment")
        lines.append(f"- Reviews analyzed: {analysis.get('reviews_count')}")
        lines.append(f"- Positive sentiment: {pos_ratio * 100:.1f}%")

        if issues:
            lines.append(f"- Top customer complaints: {', '.join(issues)}")
        else:
            lines.append("- No major customer concerns detected")

        lines.append("")
        lines.append(f"⚔️ Competitive Landscape")
        lines.append(f"- Similar competing products found: {competitors_count}")

        if avg_competitor_price:
            diff = ((my_price - avg_competitor_price) / avg_competitor_price) * 100
            sign = "+" if diff >= 0 else ""
            lines.append(f"- Competitor average price: ${avg_competitor_price:.2f} ({sign}{diff:.1f}% difference)")
        lines.append("")

        lines.append(f"💰 Pricing Recommendation")
        lines.append(f"- Suggested price: ${my_price}")

        reason = pricing.get("business_reason", [])
        if reason:
            lines.append(f"- {reason[0]}")
        else:
            lines.append("- Pricing logic could not generate a recommendation.")

        lines.append("")
        lines.append("📎 Business Summary")
        lines.append("This automated agent pipeline collects market data, reviews customer sentiment, compares pricing, and provides a data-backed recommendation for decision making.")

        return "\n".join(lines)
    
    def run(self, product_id: str):
        logger.info(f"[RUN] Starting pipeline for {product_id}")

        # Build URL
        if len(product_id) == 10 and product_id.isalnum():
            url = f"https://www.amazon.com/dp/{product_id}"
        else:
            url = f"https://mocksite.com/product/{product_id}"

        # 1. SCRAPER
        logger.info("[RUN] Stage 1 → Scraping product & reviews")
        scraper = self.discover("scraper_agent")

        prod_resp = self.call_agent(
            scraper,
            "fetch_product_page",
            {"url": url}
        )
        product = prod_resp.get("product", {})

        rev_resp = self.call_agent(
            scraper,
            "fetch_reviews",
            {"product_id": product.get("product_id")}
        )
        reviews = rev_resp.get("reviews", [])

        # 2. Compute embeddings
        logger.info("[RUN] Stage 2 → Computing embeddings")

        product_text = (
            product.get("title", "") + " " + json.dumps(product.get("specs", {}))
        ).strip()

        product_emb = embed_text(product_text)

        review_texts = [r.get("text", "") for r in reviews]
        agg_review_text = " ".join(review_texts).strip()
        agg_review_emb = embed_text(agg_review_text) if agg_review_text else None

        # 3. Store to memory
        logger.info("[RUN] Stage 3 → Persisting product info to memory")

        try:
            self.product_mem.save(
                product.get("product_id"),
                product,
                embedding=product_emb,
            )

            if agg_review_emb is not None:
                self.sentiment_mem.save(
                    product.get("product_id"),
                    {"n_reviews": len(review_texts)},
                    embedding=agg_review_emb,
                )

        except Exception as e:
            logger.exception(f"[ERROR] Failed saving product/sentiment memory: {e}")

        # 4. SENTIMENT AGENT
        logger.info("[RUN] Stage 4 → Sentiment analysis")
        
        sentiment_card = self.discover("sentiment_agent")
        sent_resp = self.call_agent(
            sentiment_card,
            "analyze_reviews",
            {"product_id": product.get("product_id"), "reviews": reviews}
        )
        sentiment = sent_resp.get("result", {})

        sent_summary = (
            f"pos_ratio={sentiment.get('positive_ratio')} "
            f"issues={','.join(sentiment.get('top_issues', []))}"
        )
        sent_emb = embed_text(sent_summary)

        try:
            self.sentiment_mem.save(
                product.get("product_id"),
                sentiment,
                embedding=sent_emb,
            )
        except Exception as e:
            logger.exception(f"[ERROR] Failed storing sentiment: {e}")

        # 5. PRICING AGENT
        logger.info("[RUN] Stage 5 → Pricing recommendation")

        pricing_card = self.discover("pricing_agent")
        price_resp = self.call_agent(
            pricing_card,
            "recommend_price",
            {
                "product": product,
                "reviews": reviews,
                "sentiment_score": sentiment.get("positive_ratio", 0.5)
            }
        )
        pricing = price_resp.get("result", {})
        
        pricing["sentiment_score"] = sentiment.get("positive_ratio")

        price_emb = embed_text(
            f"{pricing.get('recommended_price')} ratio={pricing.get('positive_ratio')}"
        )

        try:
            self.pricing_mem.save(
                product.get("product_id"),
                pricing,
                embedding=price_emb,
            )
        except Exception as e:
            logger.exception(f"[ERROR] Failed storing pricing: {e}")

        # 6. Context search (FAISS lookup)
        logger.info("[RUN] Stage 6 → Memory insights")

        try:
            similar_products = self.product_mem.search(product_emb, top_k=5)
            recent_sentiments = self.sentiment_mem.search(sent_emb, top_k=5)
            pricing_history = self.pricing_mem.search(price_emb, top_k=5)

        except Exception as e:
            logger.exception(f"[ERROR] Memory search failed: {e}")
            similar_products = []
            recent_sentiments = []
            pricing_history = []

        logger.info(f"[RUN] FINISHED pipeline for {product_id}")

        report = {
            "product": product,
            "reviews_count": len(reviews),
            "sentiment": sentiment,
            "pricing": pricing,
            "memory_insights": {
                "similar_products": similar_products,
                "recent_sentiments": recent_sentiments,
                "pricing_history": pricing_history,
            },
        }

        # Tambahkan business output
        report["business_summary"] = self.generate_business_report(report)
        
        return report

    # ------------------------------------------------------------
    #  Search workflow (scrape multiple products)
    # ------------------------------------------------------------
    def run_search(self, query: str, page: int = 1):
        logger.info(f"[SEARCH] Searching for query='{query}', page={page}")

        scraper = self.discover("scraper_agent")

        resp = self.call_agent(
            scraper,
            "search_products",
            {"query": query, "page": page},
        )

        asins = resp.get("asins", [])
        results = []

        for asin in asins:
            logger.info(f"[SEARCH] Processing ASIN={asin}")
            out = self.run(asin)
            results.append(out)

        return {
            "query": query,
            "found": len(asins),
            "asins": asins,
            "results": results,
        }

# -------------------------------------------------------------------
#  DEBUG ENTRY POINT
# -------------------------------------------------------------------
if __name__ == "__main__":
    rc = RemoteCoordinator()
    out = rc.run_search("rtx 4090", page=1)
    print(json.dumps(out, indent=2))