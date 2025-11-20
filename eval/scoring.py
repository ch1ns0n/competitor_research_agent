import json

def simple_rule_based_check(report, expected):
    score = 10
    
    # check product metadata contains keywords
    for kw in expected.get("product_contains", []):
        if kw.lower() not in json.dumps(report.get("product", "")).lower():
            score -= 3
    
    # required sections
    for section in expected.get("must_include_sections", []):
        if section not in report:
            score -= 3
    
    # sanity check for pricing
    pricing = report.get("pricing", {})
    if "recommended_price" in pricing:
        if pricing["recommended_price"] > expected["max_price"]:
            score -= 3
    
    return max(score, 1)