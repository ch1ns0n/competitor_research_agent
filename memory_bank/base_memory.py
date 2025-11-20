from abc import ABC, abstractmethod
from typing import Any, List, Dict

class BaseMemory(ABC):
    """Abstract memory interface for concrete memory stores."""

    @abstractmethod
    def add(self, metadata: Dict[str, Any], embedding: List[float] = None) -> int:
        """
        Add one record. Should return the assigned integer id.
        If embedding is None, implementation may create embedding from metadata.
        """
        raise NotImplementedError

    @abstractmethod
    def search(self, query_embedding: List[float], top_k: int = 5):
        """
        Search and return list of (metadata, distance) pairs.
        """
        raise NotImplementedError