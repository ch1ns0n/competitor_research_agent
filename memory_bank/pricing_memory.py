import os
import json
import numpy as np
from typing import Dict, Any, List

from memory_bank.base_memory import BaseMemory
from memory_bank.faiss_memory import FaissMemoryIndex
from memory_bank.metadata_utils import append_jsonl, get_by_indices, load_all

DEFAULT_DIM = 384
DEFAULT_INDEX_PATH = "memory_bank/metadata/pricing.faiss"
DEFAULT_METADATA_PATH = "memory_bank/metadata/pricing.jsonl"


class PricingMemory(BaseMemory):
    def __init__(self, dim=DEFAULT_DIM, index_path=DEFAULT_INDEX_PATH, metadata_path=DEFAULT_METADATA_PATH):
        self.index = FaissMemoryIndex(dim=dim, index_path=index_path)
        self.meta_path = metadata_path

        # Load all metadata and build lookup map
        self.key_to_index = {}
        all_metas = load_all(self.meta_path)
        for idx, item in enumerate(all_metas):
            self.key_to_index[item["key"]] = idx

    def _rewrite_metadata(self, all_items):
        with open(self.meta_path, "w", encoding="utf-8") as f:
            for item in all_items:
                f.write(json.dumps(item) + "\n")

    def _delete_existing(self, key):
        if key not in self.key_to_index:
            return

        old_index = self.key_to_index[key]

        # remove vector
        self.index.remove(np.array([old_index]))

        # remove JSON metadata
        all_items = load_all(self.meta_path)
        new_items = []
        new_map = {}
        new_idx = 0

        for item in all_items:
            if item["key"] == key:
                continue
            new_items.append(item)
            new_map[item["key"]] = new_idx
            new_idx += 1

        self._rewrite_metadata(new_items)
        self.key_to_index = new_map

    def save(self, key: str, metadata: Dict[str, Any], embedding=None) -> int:
        # wipe old version
        self._delete_existing(key)

        assigned = append_jsonl(self.meta_path, {"key": key, "metadata": metadata})
        self.key_to_index[key] = assigned

        # save vector
        if embedding is not None:
            self.index.add(np.asarray(embedding, dtype="float32"), int(assigned))

        return assigned

    def search(self, query_embedding, top_k=5) -> List[Dict[str, Any]]:
        distances, ids = self.index.search(query_embedding, top_k)
        metas = get_by_indices(self.meta_path, ids)
        return [
            {"id": idx, "distance": d, "record": m}
            for m, d, idx in zip(metas, distances, ids)
        ]