import os
import json
import numpy as np
import faiss


class ProductMemory:
    def __init__(
        self,
        dim=768,
        index_path="memory_bank/storage/faiss_product.index",
        metadata_path="memory_bank/storage/product_metadata.jsonl"
    ):
        self.dim = dim
        self.index_path = index_path
        self.metadata_path = metadata_path

        # Load or create FAISS index
        if os.path.exists(index_path):
            self.index = faiss.read_index(index_path)
        else:
            self.index = faiss.IndexFlatL2(dim)

        # Load metadata into RAM (list of dict)
        self.metadata = []
        if os.path.exists(metadata_path):
            with open(metadata_path, "r", encoding="utf-8") as f:
                for line in f:
                    self.metadata.append(json.loads(line))

    # --------------------------------------------------------
    # Save a new product to FAISS + JSONL disk metadata
    # --------------------------------------------------------
    def save(self, product_id: str, product_data: dict, embedding: np.ndarray = None):
        # no embedding → cannot index
        if embedding is None:
            print("[ProductMemory] WARNING: No embedding provided → storing metadata only.")
        else:
            if embedding.ndim == 1:
                embedding = embedding.reshape(1, -1)
            self.index.add(embedding)
            faiss.write_index(self.index, self.index_path)

        record = {
            "id": product_id,
            "data": product_data
        }
        self.metadata.append(record)
        with open(self.metadata_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    # --------------------------------------------------------
    # Search nearest products by vector similarity
    # --------------------------------------------------------
    def search(self, query_embedding: np.ndarray, top_k=5):
        if len(self.metadata) == 0 or self.index.ntotal == 0:
            return []

        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        distances, idxs = self.index.search(query_embedding, top_k)

        results = []
        for i in idxs[0]:
            if i < len(self.metadata):
                results.append(self.metadata[i])

        return results