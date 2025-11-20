import threading
import numpy as np
from typing import List
from sentence_transformers import SentenceTransformer

_MODEL_LOCK = threading.Lock()
_MODEL = None
_MODEL_NAME = "all-MiniLM-L6-v2"  # change if you want different dim

def get_embedder():
    global _MODEL
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
                _MODEL = SentenceTransformer(_MODEL_NAME)
    return _MODEL

def embed_text(text: str) -> np.ndarray:
    model = get_embedder()
    return np.asarray(model.encode(text), dtype="float32")

def embed_texts(texts: List[str]) -> np.ndarray:
    model = get_embedder()
    return np.asarray(model.encode(texts), dtype="float32")