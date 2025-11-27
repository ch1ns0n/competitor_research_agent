import os
import sys
import json
import argparse
import base64
from io import BytesIO
from statistics import mean
from collections import defaultdict

import pandas as pd
import matplotlib.pyplot as plt

# -------------------------
# Helpers
# -------------------------
def read_jsonl(path):
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                # try fallback: line may be a bare JSON dict without newline
                continue
    return items

def embed_png_figure(fig) -> str:
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"

def safe_get(d, *keys, default=None):
    x = d
    for k in keys:
        if not isinstance(x, dict):
            return default
        x = x.get(k)
        if x is None:
            return default
    return x

# -------------------------
# Build dataframes
# -------------------------
def build_dfs(records):
    # We'll produce a products list where each record is expected to already
    # contain "product", "sentiment", "pricing" per your merged schema.
    products = []
    for rec in records:
        product = rec.get("product") or {}
        pricing = rec.get("pricing") or {}
        sentiment = rec.get("sentiment") or {}
        # Some merged sources may keep metadata under memory_insights.pricing_history -> record.metadata
        products.append({
            "key": product.get("product_id") or product.get("key") or safe_get(product, "metadata", "product_id") or "UNKNOWN",
            "title": product.get("title") or safe_get(product, "metadata", "title") or "Unknown title",
            "marketplace": product.get("marketplace") or safe_get(product, "metadata", "marketplace"),
            "url": product.get("url") or safe_get(product, "metadata", "url"),
            "price": float(product.get("price") or safe_get(product, "metadata", "price") or pricing.get("base_price") or pricing.get("competitor_average_price") or 0.0),
            "rating": product.get("rating") or safe_get(product, "metadata", "rating") or None,
            "reviews_count": rec.get("reviews_count") or safe_get(sentiment, "n_reviews") or 0,
            "positive_ratio": float(sentiment.get("positive_ratio") if sentiment.get("positive_ratio") is not None else (pricing.get("sentiment_score") or 0.5)),
            "recommended_price": float(pricing.get("recommended_price") or pricing.get("base_price") or 0.0),
            "competitor_average_price": (float(pricing.get("competitor_average_price")) if pricing.get("competitor_average_price") not in (None, "null") else None),
            "business_reason": pricing.get("business_reason") or []
        })
    df = pd.DataFrame(products)
    return df

# -------------------------
# Charts
# -------------------------
def chart_price_vs_competitor(df):
    # choose top N products by price diff magnitude for visualization
    df_chart = df.dropna(subset=["competitor_average_price"]).copy()
    if df_chart.empty:
        # fallback: plot histogram of recommended_price
        fig, ax = plt.subplots(figsize=(6,3))
        ax.hist(df["recommended_price"].dropna(), bins=12)
        ax.set_title("Recommended price distribution")
        ax.set_xlabel("USD")
        ax.set_ylabel("Count")
        fig.tight_layout()
        return fig

    df_chart["gap_pct"] = (df_chart["recommended_price"] - df_chart["competitor_average_price"]) / df_chart["competitor_average_price"]
    df_chart = df_chart.reindex(df_chart["gap_pct"].abs().sort_values(ascending=False).index).head(12)
    labels = [ (t[:40] + "...") if len(t) > 40 else t for t in df_chart["title"].tolist() ]

    fig, ax = plt.subplots(figsize=(10, 3 + len(df_chart)*0.35))
    x = range(len(df_chart))
    ax.barh(x, df_chart["recommended_price"], label="Recommended", alpha=0.9)
    ax.barh(x, df_chart["competitor_average_price"], label="Competitor Avg", alpha=0.5)
    ax.set_yticks(x)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("USD")
    ax.set_title("Recommended price vs Competitor average (top gaps)")
    ax.legend()
    fig.tight_layout()
    return fig

def chart_sentiment_distribution(df):
    fig, ax = plt.subplots(figsize=(6,3))
    vals = df["positive_ratio"].dropna().clip(0,1)
    ax.hist(vals, bins=[0,0.2,0.4,0.6,0.75,0.85,1.0])
    ax.set_title("Sentiment distribution (positive_ratio)")
    ax.set_xlabel("Positive ratio")
    ax.set_ylabel("Count")
    fig.tight_layout()
    return fig

# -------------------------
# HTML Renderer
# -------------------------
HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Dark Tech — Competitor Pricing Report</title>
<style>
:root {{
  --bg: #0f1115;
  --card: #0b0d10;
  --muted: #99a1ad;
  --accent: #6ee7b7;
  --danger: #ff6b6b;
  --glass: rgba(255,255,255,0.03);
}}
body {{ background: linear-gradient(180deg,#07080a 0%, #0f1115 100%); color:#e6eef6; font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; margin:0; padding:24px; }}
.container {{ max-width:1200px; margin:0 auto; }}
.header {{ display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:18px; }}
.brand {{ font-weight:700; font-size:20px; color:var(--accent); }}
.subtitle {{ color:var(--muted); font-size:13px; }}
.grid {{ display:grid; grid-template-columns: 1fr 360px; gap:18px; align-items:start; }}
.card {{ background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)); border:1px solid rgba(255,255,255,0.04); padding:16px; border-radius:12px; box-shadow: 0 6px 22px rgba(2,6,23,0.6); }}
.small {{ font-size:13px; color:var(--muted); }}
.h1 {{ font-size:18px; margin:0 0 8px 0; }}
.product-list {{ display:flex; flex-direction:column; gap:10px; max-height: 720px; overflow:auto; padding-right:6px; }}
.product-card {{ display:flex; gap:12px; align-items:flex-start; border-radius:10px; padding:12px; background:var(--glass); border:1px solid rgba(255,255,255,0.02); }}
.product-meta {{ flex:1; }}
.title {{ font-weight:700; color:#fff; margin:0 0 6px 0; font-size:14px; }}
.meta-row {{ color:var(--muted); font-size:12px; display:flex; gap:10px; flex-wrap:wrap; }}
.reason {{ color:var(--muted); font-size:12px; margin-top:8px; }}
.kpi {{ display:flex; gap:12px; align-items:center; }}
.kpi .num {{ font-weight:700; color:var(--accent); }}
.badge {{ background: rgba(255,255,255,0.03); padding:6px 8px; border-radius:8px; font-size:12px; color:var(--muted); }}
.footer {{ margin-top:18px; font-size:12px; color:var(--muted); }}
.chart {{ width:100%; border-radius:8px; overflow:hidden; }}
.top-insight {{ font-size:13px; color:var(--accent); font-weight:700; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <div class="brand">Dark Tech — Competitor Pricing Report</div>
      <div class="subtitle">Auto-generated — products: {n_products} • avg price: ${avg_price:.2f} • avg sentiment: {avg_sentiment:.2f}</div>
    </div>
    <div class="kpi">
      <div class="badge">Products: {n_products}</div>
      <div class="badge">Market avg: ${avg_price:.2f}</div>
      <div class="badge">Avg sentiment: {avg_sentiment:.2f}</div>
    </div>
  </div>

  <div class="grid">
    <div>
      <div class="card">
        <div class="h1">Market overview</div>
        <div class="small">Top insights</div>
        <ol>
          {top_insights}
        </ol>
        <div style="margin-top:12px;">
          <div class="small">Pricing vs competitor</div>
          <div class="chart"><img src="{chart_price}" alt="price chart" style="width:100%; height:auto; display:block;"/></div>
        </div>
        <div style="margin-top:12px;">
          <div class="small">Sentiment distribution</div>
          <div class="chart"><img src="{chart_sentiment}" alt="sent chart" style="width:100%; height:auto; display:block;"/></div>
        </div>
      </div>

      <div style="height:16px"></div>

      <div class="card">
        <div class="h1">Products</div>
        <div class="product-list">
          {product_cards}
        </div>
      </div>
    </div>

    <div>
      <div class="card">
        <div class="h1">Highlights</div>
        <div class="small">Most underpriced (largest positive gap vs competitor avg)</div>
        <div style="margin:10px 0;">
          {most_underpriced}
        </div>

        <div style="height:12px"></div>

        <div class="small">Most overpriced (largest negative gap)</div>
        <div style="margin:10px 0;">
          {most_overpriced}
        </div>

        <div style="height:12px"></div>

        <div class="small">Recommendation summary</div>
        <ul>
          {rec_summary}
        </ul>
      </div>
    </div>
  </div>

  <div class="footer">Generated by Dark Tech — Multi-agent pricing pipeline</div>
</div>
</body>
</html>
"""

# -------------------------
# Template pieces
# -------------------------
def render_product_card(row):
    title = row["title"]
    url = row.get("url") or "#"
    price = row.get("price") or 0.0
    rec = row.get("recommended_price") or 0.0
    comp = row.get("competitor_average_price")
    pr = row.get("positive_ratio") or 0.0
    reasons = row.get("business_reason") or []
    reasons_html = "<br/>".join(f"- {r}" for r in reasons[:3]) if reasons else "—"
    comp_text = f"${comp:.2f}" if comp is not None else "N/A"

    html = f"""
    <div class="product-card">
      <div style="width:8px;height:8px;border-radius:50%;background:var(--accent);margin-top:6px;"></div>
      <div class="product-meta">
        <div class="title"><a href="{url}" target="_blank" style="color:inherit;text-decoration:none;">{title}</a></div>
        <div class="meta-row">
          <div class="badge">Price: ${price:.2f}</div>
          <div class="badge">Rec: ${rec:.2f}</div>
          <div class="badge">Comp avg: {comp_text}</div>
          <div class="badge">Sent: {pr:.2f}</div>
        </div>
        <div class="reason">{reasons_html}</div>
      </div>
    </div>
    """
    return html

# -------------------------
# Main
# -------------------------
def generate_report(input_path, output_path):
    records = read_jsonl(input_path)
    if not records:
        print("No records found in", input_path)
        return

    df = build_dfs(records)

    # market stats
    n_products = len(df)
    avg_price = float(df["price"].replace(0, pd.NA).dropna().mean() or 0.0)
    avg_sentiment = float(df["positive_ratio"].mean() or 0.0)

    # charts
    fig_price = chart_price_vs_competitor(df)
    img_price = embed_png_figure(fig_price)

    fig_sent = chart_sentiment_distribution(df)
    img_sent = embed_png_figure(fig_sent)

    # top insights
    insights = []
    # 1. biggest gaps (recommended vs competitor avg)
    df_valid_comp = df.dropna(subset=["competitor_average_price"]).copy()
    if not df_valid_comp.empty:
        df_valid_comp["gap_pct"] = (df_valid_comp["recommended_price"] - df_valid_comp["competitor_average_price"]) / df_valid_comp["competitor_average_price"]
        top_under = df_valid_comp.sort_values("gap_pct", ascending=False).head(3)
        top_over = df_valid_comp.sort_values("gap_pct", ascending=True).head(3)
        insights.append(f"Top underpriced products (by %): {', '.join(top_under['key'].tolist())}")
        insights.append(f"Top overpriced products (by %): {', '.join(top_over['key'].tolist())}")
    else:
        insights.append("No competitor average prices available to compute market gaps.")

    insights.append(f"Average recommended price: ${df['recommended_price'].replace(0,pd.NA).dropna().mean():.2f}")
    insights.append(f"Sentiment average: {avg_sentiment:.2f}")

    top_insights_html = "".join(f"<li>{i}</li>" for i in insights)

    # product cards
    product_cards = "\n".join(render_product_card(r) for _, r in df.sort_values("recommended_price", ascending=False).head(60).iterrows())

    # highlights
    most_underpriced = "—"
    most_overpriced = "—"
    rec_summary = []
    if not df_valid_comp.empty:
        u = df_valid_comp.sort_values("gap_pct", ascending=False).head(1)
        o = df_valid_comp.sort_values("gap_pct", ascending=True).head(1)
        if not u.empty:
            row = u.iloc[0]
            most_underpriced = f"<div><b>{row['key']}</b> rec ${row['recommended_price']:.2f} vs comp ${row['competitor_average_price']:.2f} ({row['gap_pct']*100:.1f}%)</div>"
            rec_summary.append("Consider measured price increases for underpriced / high-sentiment products.")
        if not o.empty:
            row = o.iloc[0]
            most_overpriced = f"<div><b>{row['key']}</b> rec ${row['recommended_price']:.2f} vs comp ${row['competitor_average_price']:.2f} ({row['gap_pct']*100:.1f}%)</div>"
            rec_summary.append("Review overstated prices where sentiment is weak.")
    else:
        rec_summary.append("Insufficient competitor price data; focus on improving coverage.")

    rec_summary_html = "".join(f"<li>{s}</li>" for s in rec_summary)

    html = HTML_TEMPLATE.format(
        n_products=n_products,
        avg_price=avg_price,
        avg_sentiment=avg_sentiment,
        top_insights=top_insights_html,
        chart_price=img_price,
        chart_sentiment=img_sent,
        product_cards=product_cards,
        most_underpriced=most_underpriced,
        most_overpriced=most_overpriced,
        rec_summary=rec_summary_html
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report written to {output_path}")

# -------------------------
# CLI
# -------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", required=True, help="merged.jsonl input (one JSON per line)")
    parser.add_argument("--output", "-o", default="report.html", help="output HTML path")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print("Input file not found:", args.input)
        sys.exit(1)

    generate_report(args.input, args.output)

if __name__ == "__main__":
    main()