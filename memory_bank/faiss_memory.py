import os
import faiss
import numpy as np
import tempfile
import threading
import logging

logger = logging.getLogger(__name__)
_index_lock = threading.Lock()

class FaissMemoryIndex:
    """
    Thin wrapper around a FAISS IndexIDMap(IndexFlatL2) with persistent save/load.
    We map record IDs (int) to the vectors explicitly so index id = metadata id.
    """

    def __init__(self, dim: int = 384, index_path: str = "memory_bank/metadata/_faiss.index"):
        self.dim = dim
        self.index_path = index_path
        os.makedirs(os.path.dirname(index_path), exist_ok=True)

        if os.path.exists(index_path):
            try:
                self.index = faiss.read_index(index_path)
            except Exception as e:
                logger.exception("Failed to read FAISS index, rebuilding. Error: %s", e)
                self.index = faiss.IndexIDMap(faiss.IndexFlatL2(dim))
        else:
            self.index = faiss.IndexIDMap(faiss.IndexFlatL2(dim))

    def add(self, vector: np.ndarray, idx: int):
        """
        Add single vector with explicit id.
        vector: 1-D numpy float32 array (dim,)
        idx: integer id (metadata id)
        """
        if vector is None:
            raise ValueError("vector is None")

        vec = np.asarray(vector, dtype="float32").reshape(1, -1)
        ids = np.array([idx], dtype="int64")
        with _index_lock:
            self.index.add_with_ids(vec, ids)
            self._save_index_atomic()

    def add_batch(self, vectors: np.ndarray, ids: np.ndarray):
        """
        Add multiple vectors; vectors shape (n,d), ids shape (n,)
        """
        with _index_lock:
            self.index.add_with_ids(vectors.astype("float32"), ids.astype("int64"))
            self._save_index_atomic()

    def search(self, vector: np.ndarray, top_k: int = 5):
        """
        Return (distances, ids) arrays for top_k nearest neighbors.
        """
        if vector is None:
            return [], []
        query = np.asarray(vector, dtype="float32").reshape(1, -1)
        with _index_lock:
            D, I = self.index.search(query, top_k)
        return D[0].tolist(), I[0].tolist()

    def _save_index_atomic(self):
        # atomic write to disk
        tmp = tempfile.NamedTemporaryFile(delete=False, dir=os.path.dirname(self.index_path))
        tmp_name = tmp.name
        tmp.close()
        faiss.write_index(self.index, tmp_name)
        os.replace(tmp_name, self.index_path)