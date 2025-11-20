import numpy as np
from typing import Dict, Any, List
from memory_bank.base_memory import BaseMemory
from memory_bank.faiss_memory import FaissMemoryIndex
from memory_bank.metadata_utils import append_jsonl, get_by_indices

DEFAULT_DIM = 384
DEFAULT_INDEX_PATH = "memory_bank/metadata/pricing.faiss"
DEFAULT_METADATA_PATH = "memory_bank/metadata/pricing.jsonl"

class PricingMemory(BaseMemory):
    def __init__(self, dim=DEFAULT_DIM, index_path=DEFAULT_INDEX_PATH, metadata_path=DEFAULT_METADATA_PATH):
        self.index = FaissMemoryIndex(dim=dim, index_path=index_path)
        self.meta_path = metadata_path

    def save(self, key: str, metadata: Dict[str, Any], embedding=None) -> int:
        assigned = append_jsonl(self.meta_path, {"key": key, "metadata": metadata})
        if embedding is not None:
            self.index.add(np.asarray(embedding, dtype="float32"), int(assigned))
        return assigned

    def search(self, query_embedding, top_k=5) -> List[Dict[str, Any]]:
        distances, ids = self.index.search(query_embedding, top_k)
        metas = get_by_indices(self.meta_path, ids)
        return [{"id": idx, "distance": d, "record": m} for m, d, idx in zip(metas, distances, ids)]