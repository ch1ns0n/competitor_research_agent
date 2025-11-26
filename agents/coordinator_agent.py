import os
import json
import time
import uuid
import requests

from infra.embedding import embed_text
from memory_bank.product_memory import ProductMemory
from memory_bank.sentiment_memory import SentimentMemory
from memory_bank.pricing_memory import PricingMemory

from scrapers.logger import get_logger

API_KEY = os.getenv("A2A_API_KEY", "secret")
REGISTRY_URL = os.getenv("AGENT_REGISTRY_URL", "http://localhost:9000")
logger = get_logger("coordinator_agent")


# ============================================================
#  Tracing Utilities
# ============================================================

class PipelineContext:
    """Shared context for each product pipeline."""
    def __init__(self, product_id: str):
        self.trace_id = str(uuid.uuid4())[:8]
        self.product_id = product_id
        self.stage = None

    def log(self, message: str, **extra):
        payload = {
            "trace_id": self.trace_id,
            "product_id": self.product_id,
            "stage": self.stage,
            "msg": message,
        }
        payload.update(extra)
        logger.info(json.dumps(payload))


def trace_stage(stage_name):
    """Decorator untuk logging start/end + duration untuk tiap stage pipeline."""
    def wrapper(fn):
        def inner(self, ctx: PipelineContext, *args, **kwargs):
            ctx.stage = stage_name
            start = time.time()
            ctx.log(f"[START] {stage_name}")
            try:
                result = fn(self, ctx, *args, **kwargs)
            except Exception as e:
                ctx.log(f"[ERROR] {stage_name}", error=str(e))
                raise
            finally:
                duration = round((time.time() - start) * 1000, 2)
                ctx.log(f"[END] {stage_name}", duration_ms=duration)
            return result
        return inner
    return wrapper


def trace_a2a_call(task_name):
    """Decorator untuk logging panggilan A2A antara agents."""
    def wrapper(fn):
        def inner(self, ctx: PipelineContext, *args, **kwargs):
            ctx.log(f"[A2A] CALL {task_name}")
            start = time.time()
            try:
                result = fn(self, ctx, *args, **kwargs)
                return result
            except Exception as e:
                ctx.log(f"[ERROR] A2A {task_name}", error=str(e))
                raise
            finally:
                duration = round((time.time() - start) * 1000, 2)
                ctx.log(f"[A2A] FINISH {task_name}", duration_ms=duration)
        return inner
    return wrapper


# ============================================================
#  Coordinator
# ============================================================

class RemoteCoordinator:
    def __init__(self, registry_url: str = REGISTRY_URL):
        self.registry_url = registry_url

        self.product_mem = ProductMemory()
        self.sentiment_mem = SentimentMemory()
        self.pricing_mem = PricingMemory()

    # -----------------------------
    # Discover agent
    # -----------------------------
    @trace_a2a_call("discover_agent")
    def discover(self, ctx: PipelineContext, agent_name: str):
        ctx.log(f"[DISCOVER] Looking up agent `{agent_name}`")

        r = requests.get(f"{self.registry_url}/agents/{agent_name}", timeout=5)
        r.raise_for_status()
        card = r.json()

        base = card.get("agent_url") or card.get("url")
        ctx.log(f"[DISCOVER] Found `{agent_name}`", url=base)

        return {"agent_url": base}

    # -----------------------------
    # Remote call
    # -----------------------------
    @trace_a2a_call("call_agent")
    def call_agent(self, ctx: PipelineContext, card, task: str, input_payload: dict):
        base = card.get("agent_url")
        exec_url = base.rstrip("/") + "/a2a/execute"

        ctx.log(f"[CALL] POST {task}", url=exec_url)

        payload = {"task": task, "input": input_payload}
        headers = {"X-API-KEY": API_KEY}

        response = requests.post(exec_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        ctx.log(f"[CALL] SUCCESS {task}")
        return response.json()

    # ============================================================
    #  Pipeline Stages
    # ============================================================

    @trace_stage("SCRAPER")
    def stage_scraper(self, ctx, product_id, url):
        scraper = self.discover(ctx, "scraper_agent")

        prod_resp = self.call_agent(ctx, scraper, "fetch_product_page", {"url": url})
        product = prod_resp.get("product", {})

        rev_resp = self.call_agent(
            ctx, scraper, "fetch_reviews", {"product_id": product.get("product_id")}
        )
        reviews = rev_resp.get("reviews", [])

        return product, reviews

    @trace_stage("EMBEDDINGS")
    def stage_embeddings(self, ctx, product, reviews):
        product_text = (
            product.get("title", "") + " " + json.dumps(product.get("specs", {}))
        ).strip()
        product_emb = embed_text(product_text)

        review_texts = [r.get("text", "") for r in reviews]
        agg_review_text = " ".join(review_texts).strip()
        agg_review_emb = embed_text(agg_review_text) if agg_review_text else None

        return product_emb, agg_review_emb

    @trace_stage("MEMORY_SAVE")
    def stage_memory_store(self, ctx, product, reviews, product_emb, agg_emb):
        try:
            self.product_mem.save(product.get("product_id"), product, embedding=product_emb)

            if agg_emb is not None:
                self.sentiment_mem.save(
                    product.get("product_id"), {"n_reviews": len(reviews)}, embedding=agg_emb
                )
        except Exception as e:
            ctx.log("[ERROR] Failed saving memories", error=str(e))

    @trace_stage("SENTIMENT")
    def stage_sentiment(self, ctx, product, reviews):
        card = self.discover(ctx, "sentiment_agent")
        resp = self.call_agent(
            ctx,
            card,
            "analyze_reviews",
            {"product_id": product.get("product_id"), "reviews": reviews},
        )
        sentiment = resp.get("result", {})

        # store sentiment embedding
        summary = (
            f"pos_ratio={sentiment.get('positive_ratio')} "
            f"issues={','.join(sentiment.get('top_issues', []))}"
        )
        emb = embed_text(summary)

        try:
            self.sentiment_mem.save(product.get("product_id"), sentiment, embedding=emb)
        except:
            pass

        return sentiment, emb

    @trace_stage("PRICING")
    def stage_pricing(self, ctx, product, reviews, sentiment):
        card = self.discover(ctx, "pricing_agent")
        resp = self.call_agent(
            ctx,
            card,
            "recommend_price",
            {
                "product": product,
                "reviews": reviews,
                "sentiment_score": sentiment.get("positive_ratio", 0.5),
            },
        )
        pricing = resp.get("result", {})
        pricing["sentiment_score"] = sentiment.get("positive_ratio")

        emb = embed_text(f"{pricing.get('recommended_price')} ratio={pricing.get('positive_ratio')}")

        try:
            self.pricing_mem.save(product.get("product_id"), pricing, embedding=emb)
        except:
            pass

        return pricing, emb

    @trace_stage("MEMORY_INSIGHTS")
    def stage_memory_insights(self, ctx, product_emb, sent_emb, pricing_emb):
        try:
            similar_products = self.product_mem.search(product_emb, top_k=5)
            recent_sentiments = self.sentiment_mem.search(sent_emb, top_k=5)
            pricing_history = self.pricing_mem.search(pricing_emb, top_k=5)
        except Exception as e:
            ctx.log("[ERROR] Memory search", error=str(e))
            return [], [], []

        return similar_products, recent_sentiments, pricing_history

    # ============================================================
    #  Report Builder
    # ============================================================

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
        lines.append("📌 PRODUCT ANALYSIS REPORT")
        lines.append(f"Product: {product.get('title')}")
        lines.append(f"Marketplace: {product.get('marketplace')}")
        lines.append(f"Price: ${product.get('price')}")
        lines.append(f"Rating: {product.get('rating')} ⭐")
        lines.append("")

        lines.append("📊 Market Sentiment")
        lines.append(f"- Reviews analyzed: {analysis.get('reviews_count')}")
        lines.append(f"- Positive sentiment: {pos_ratio * 100:.1f}%")

        if issues:
            lines.append(f"- Top customer complaints: {', '.join(issues)}")
        else:
            lines.append("- No major customer concerns detected")

        lines.append("")
        lines.append("⚔️ Competitive Landscape")
        lines.append(f"- Similar competing products found: {competitors_count}")

        if avg_competitor_price:
            diff = ((my_price - avg_competitor_price) / avg_competitor_price) * 100
            sign = "+" if diff >= 0 else ""
            lines.append(f"- Competitor average price: ${avg_competitor_price:.2f} ({sign}{diff:.1f}% difference)")
        lines.append("")

        lines.append("💰 Pricing Recommendation")
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

    # ============================================================
    #  Pipeline Runner
    # ============================================================

    def run(self, product_id: str):
        ctx = PipelineContext(product_id)
        ctx.log("[PIPELINE] START")

        # build Amazon URL
        if len(product_id) == 10 and product_id.isalnum():
            url = f"https://www.amazon.com/dp/{product_id}"
        else:
            url = f"https://mocksite.com/product/{product_id}"

        # Stage 1 → Scraper
        product, reviews = self.stage_scraper(ctx, product_id, url)

        # Stage 2 → Embeddings
        product_emb, agg_review_emb = self.stage_embeddings(ctx, product, reviews)

        # Stage 3 → Save to memory
        self.stage_memory_store(ctx, product, reviews, product_emb, agg_review_emb)

        # Stage 4 → Sentiment
        sentiment, sent_emb = self.stage_sentiment(ctx, product, reviews)

        # Stage 5 → Pricing
        pricing, pricing_emb = self.stage_pricing(ctx, product, reviews, sentiment)

        # Stage 6 → Memory Insights
        similar_products, recent_sentiments, pricing_history = self.stage_memory_insights(
            ctx, product_emb, sent_emb, pricing_emb
        )

        ctx.log("[PIPELINE] END")

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

        report["business_summary"] = self.generate_business_report(report)
        return report

    # ============================================================
    #  Search Flow
    # ============================================================
    def run_search(self, query: str, page: int = 1):
        ctx = PipelineContext(f"search:{query}")
        ctx.log(f"[SEARCH] query='{query}', page={page}")

        scraper = self.discover(ctx, "scraper_agent")

        resp = self.call_agent(ctx, scraper, "search_products", {"query": query, "page": page})
        asins = resp.get("asins", [])
        results = []

        for asin in asins:
            ctx.log("[SEARCH] Processing", asin=asin)
            results.append(self.run(asin))

        return {
            "query": query,
            "found": len(asins),
            "asins": asins,
            "results": results,
        }


# ============================================================
#  CLI
# ============================================================

if __name__ == "__main__":
    rc = RemoteCoordinator()
    out = rc.run_search("rtx 4090", page=1)
    print(json.dumps(out, indent=2))