from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseMemory(ABC):
    @abstractmethod
    def save(self, key: str, metadata: Dict[str, Any], embedding=None) -> int:
        """Store metadata and optional embedding. Return assigned id (int)."""
        raise NotImplementedError

    @abstractmethod
    def search(self, query_embedding, top_k: int = 5) -> List[Dict[str, Any]]:
        """Return list of metadata (with distance optionally)"""
        raise NotImplementedError