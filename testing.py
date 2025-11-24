from memory_bank.product_memory import ProductMemory
from infra.embedding import embed_text as embed

mem = ProductMemory("metadata/product")

query = "RTX 4090 GPU"
result = mem.search(embed(query), top_k=3)

print(result)