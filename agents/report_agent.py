import json
from datetime import datetime

class ReportAgent:
    def __init__(self):
        pass

    def make_report(self, aggregation):
        p = aggregation["product"]
        s = aggregation["sentiment"]
        pr = aggregation["pricing"]
        md = f"# Product Intelligence Report: {p.get('title')}\n\n"
        md += f"**Product ID:** {p.get('product_id')}\n\n"
        md += f"**Top specs:** {json.dumps(p.get('specs',{}))}\n\n"
        md += f"## Sentiment\n- Reviews: {s.get('n_reviews')}\n- Positive ratio: {s.get('positive_ratio'):.2f}\n- Top issues: {', '.join(s.get('top_issues',[])) or 'None'}\n\n"
        md += f"## Pricing\n- Base price: {pr.get('base_price')}\n- Recommended: {pr.get('recommended_price')}\n"
        md += f"\n_Report generated: {datetime.utcnow().isoformat()}Z_\n"
        return md