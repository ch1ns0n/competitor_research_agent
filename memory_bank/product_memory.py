import os
import json
import numpy as np
from typing import Dict, Any, List
from memory_bank.base_memory import BaseMemory
from memory_bank.faiss_memory import FaissMemoryIndex
from memory_bank.metadata_utils import append_jsonl, get_by_indices, load_all

DEFAULT_DIM = 384
DEFAULT_INDEX_PATH = "memory_bank/metadata/product.faiss"
DEFAULT_METADATA_PATH = "memory_bank/metadata/product.jsonl"


class ProductMemory(BaseMemory):
    def __init__(self, dim=DEFAULT_DIM, index_path=DEFAULT_INDEX_PATH, metadata_path=DEFAULT_METADATA_PATH):
        self.dim = dim
        self.index = FaissMemoryIndex(dim=dim, index_path=index_path)
        self.meta_path = metadata_path

        # load metadata → build key → index mapping
        self.key_to_index = {}
        all_metas = load_all(self.meta_path)
        for idx, item in enumerate(all_metas):
            self.key_to_index[item["key"]] = idx

    def _rewrite_metadata(self, all_items):
        """Rewrite JSONL metadata file (overwrite)."""
        with open(self.meta_path, "w", encoding="utf-8") as f:
            for item in all_items:
                f.write(json.dumps(item) + "\n")

    def _delete_existing(self, key):
        """Remove embedding + metadata if key already exists."""
        if key not in self.key_to_index:
            return

        old_index = self.key_to_index[key]

        # remove vector from FAISS
        self.index.remove(np.array([old_index]))

        # remove metadata row
        all_items = load_all(self.meta_path)
        new_items = []
        new_map = {}
        new_idx = 0

        for i, item in enumerate(all_items):
            if item["key"] == key:
                continue
            new_items.append(item)
            new_map[item["key"]] = new_idx
            new_idx += 1

        # replace jsonl file
        self._rewrite_metadata(new_items)
        self.key_to_index = new_map

    def save(self, key: str, metadata: Dict[str, Any], embedding=None) -> int:
        """
        Save metadata and FAISS embedding, replacing old one if exists.
        """
        # delete previous version first
        self._delete_existing(key)

        # append metadata
        assigned_id = append_jsonl(self.meta_path, {"key": key, "metadata": metadata})

        # sync mapping
        self.key_to_index[key] = assigned_id

        # add new vector
        if embedding is not None:
            self.index.add(np.asarray(embedding, dtype="float32"), int(assigned_id))

        return assigned_id

    def search(self, query_embedding, top_k=5) -> List[Dict[str, Any]]:
        distances, ids = self.index.search(query_embedding, top_k)
        metas = get_by_indices(self.meta_path, ids)
        result = []
        for m, d, idx in zip(metas, distances, ids):
            result.append({"id": idx, "distance": d, "record": m})
        return result