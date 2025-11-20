import json, os, numpy as np
from infra.embedding import embed_text
from memory_bank.faiss_memory import FaissMemoryIndex
from memory_bank.metadata_utils import load_all

def reindex_product():
    meta_path = "memory_bank/metadata/product.jsonl"
    items = load_all(meta_path)
    dim = 384
    index = FaissMemoryIndex(dim=dim, index_path="memory_bank/metadata/product.faiss")
    # clear index by creating fresh object
    index.index = index.index.__class__(index.index.d) if False else index.index  # noop to keep type
    ids = []
    vecs = []
    for i, rec in enumerate(items):
        text = rec.get("metadata", {}).get("title","") + " " + json.dumps(rec.get("metadata", {}).get("specs", {}))
        v = embed_text(text)
        vecs.append(v)
        ids.append(i)
    if vecs:
        import numpy as np
        index.add_batch(np.vstack(vecs), np.array(ids))
    print("Reindex done")

if __name__ == "__main__":
    reindex_product()