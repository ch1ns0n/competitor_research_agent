import os, tempfile, threading
import faiss
import numpy as np

_index_lock = threading.Lock()

class FaissMemoryIndex:
    def __init__(self, dim: int = 384, index_path: str = "memory_bank/metadata/_faiss.index"):
        self.dim = dim
        self.index_path = index_path
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        if os.path.exists(self.index_path):
            try:
                self.index = faiss.read_index(self.index_path)
            except Exception:
                # fallback to fresh index
                self.index = faiss.IndexIDMap(faiss.IndexFlatL2(dim))
        else:
            self.index = faiss.IndexIDMap(faiss.IndexFlatL2(dim))

    def add(self, vector: np.ndarray, idx: int):
        vec = np.asarray(vector, dtype="float32").reshape(1, -1)
        ids = np.array([idx], dtype="int64")
        with _index_lock:
            self.index.add_with_ids(vec, ids)
            self._save_atomic()

    def add_batch(self, vectors: np.ndarray, ids: np.ndarray):
        with _index_lock:
            self.index.add_with_ids(vectors.astype("float32"), ids.astype("int64"))
            self._save_atomic()

    def search(self, vector: np.ndarray, top_k: int = 5):
        if vector is None:
            return [], []
        q = np.asarray(vector, dtype="float32").reshape(1, -1)
        with _index_lock:
            D, I = self.index.search(q, top_k)
        return D[0].tolist(), I[0].tolist()

    def _save_atomic(self):
        tmp = tempfile.NamedTemporaryFile(delete=False, dir=os.path.dirname(self.index_path))
        tmp_name = tmp.name
        tmp.close()
        faiss.write_index(self.index, tmp_name)
        os.replace(tmp_name, self.index_path)