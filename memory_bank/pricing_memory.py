import logging
from typing import Dict, Any
import numpy as np
from sentence_transformers import SentenceTransformer

from memory_bank.base_memory import BaseMemory
from memory_bank.faiss_memory import FaissMemoryIndex
from memory_bank.metadata_utils import append_metadata, get_multiple_metadata

logger = logging.getLogger(__name__)

DEFAULT_DIM = 384
DEFAULT_INDEX_PATH = "memory_bank/metadata/pricing.faiss"
DEFAULT_METADATA_PATH = "memory_bank/metadata/pricing.json"

class PricingMemory(BaseMemory):
    def __init__(self, dim: int = DEFAULT_DIM,
                 index_path: str = DEFAULT_INDEX_PATH,
                 metadata_path: str = DEFAULT_METADATA_PATH,
                 embedder: SentenceTransformer = None):
        self.dim = dim
        self.index = FaissMemoryIndex(dim=dim, index_path=index_path)
        self.metadata_path = metadata_path
        self._embedder = embedder

    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
        return self._embedder

    def _make_embedding_from_price(self, metadata: Dict[str, Any]):
        # canonical textual representation for price + signals
        text = f"{metadata.get('recommended_price','') } price {metadata.get('positive_ratio','')}"
        emb = self.embedder.encode(text)
        return emb.astype("float32")

    def add(self, metadata: Dict[str, Any], embedding: np.ndarray = None) -> int:
        if "timestamp" not in metadata:
            from datetime import datetime
            metadata["timestamp"] = datetime.utcnow().isoformat()

        assigned_id = append_metadata(self.metadata_path, metadata)
        if embedding is None:
            embedding = self._make_embedding_from_price(metadata)
        self.index.add(embedding, int(assigned_id))
        logger.debug("PricingMemory: added id=%s product_id=%s price=%s", assigned_id, metadata.get("product_id"), metadata.get("recommended_price"))
        return assigned_id

    def search(self, query: str = None, query_embedding: np.ndarray = None, top_k: int = 5):
        if query_embedding is None:
            if query is None:
                raise ValueError("Either query or query_embedding must be provided")
            emb = self.embedder.encode(query).astype("float32")
        else:
            emb = np.asarray(query_embedding, dtype="float32")

        distances, ids = self.index.search(emb, top_k)
        metas = get_multiple_metadata(self.metadata_path, ids)
        return [{"metadata": m, "distance": d} for m, d in zip(metas, distances)]