from abc import ABC, abstractmethod
from src.core.domain.chunk import Chunk
from typing import List, Dict, Any, Optional

class IVectorStore(ABC):
    @abstractmethod
    def upsert(self, collection_id: str, chunks: List[Chunk]) -> None:
        """Inserta fragmentos en una colección específica."""
        pass

    @abstractmethod
    def search(
        self,
        collection_id: str,
        query_vector: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        pass