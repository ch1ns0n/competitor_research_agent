import json
from collections import defaultdict

INPUT_PRODUCT = "product.jsonl"
INPUT_PRICING = "pricing.jsonl"
INPUT_SENTIMENT = "sentiment.jsonl"
OUTPUT_MERGED = "merged.jsonl"

def read_jsonl(path):
    data = defaultdict(list)
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            key = obj["key"]
            data[key].append(obj["metadata"])
    return data

def consolidate_metadata(list_of_entries):
    """
    Jika ada banyak entri dengan metadata berbeda,
    kita merge dengan rule:
    - value terakhir override yang sebelumnya
    - kecuali list, akan di-extend
    - kecuali angka harga: kita simpan max historical price
    """
    final = {}

    for entry in list_of_entries:
        for k, v in entry.items():

            # Special rule for price
            if k in ("price", "base_price", "recommended_price"):
                # keep highest historical price
                if k not in final:
                    final[k] = v
                else:
                    try:
                        final[k] = max(final[k], v)
                    except:
                        final[k] = v
                continue

            # For list → extend
            if isinstance(v, list):
                if k not in final:
                    final[k] = []
                final[k].extend(v)
                continue

            # Default: override with newest
            final[k] = v

    return final


def main():

    print("Loading product.jsonl...")
    product_data = read_jsonl(INPUT_PRODUCT)

    print("Loading pricing.jsonl...")
    pricing_data = read_jsonl(INPUT_PRICING)

    print("Loading sentiment.jsonl...")
    sentiment_data = read_jsonl(INPUT_SENTIMENT)

    all_keys = set(product_data.keys()) | set(pricing_data.keys()) | set(sentiment_data.keys())
    print(f"Found {len(all_keys)} unique products.")

    with open(OUTPUT_MERGED, "w", encoding="utf-8") as out:
        for key in sorted(all_keys):
            combined_entries = []

            if key in product_data:
                combined_entries.extend(product_data[key])
            if key in pricing_data:
                combined_entries.extend(pricing_data[key])
            if key in sentiment_data:
                combined_entries.extend(sentiment_data[key])

            merged_metadata = consolidate_metadata(combined_entries)

            final_obj = {
                "key": key,
                "metadata": merged_metadata
            }

            out.write(json.dumps(final_obj) + "\n")

    print(f"\n✅ DONE! File merged berhasil dibuat: {OUTPUT_MERGED}")
    print(f"   Total produk: {len(all_keys)}")


if __name__ == "__main__":
    main()