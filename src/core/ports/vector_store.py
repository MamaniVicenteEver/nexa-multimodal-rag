from abc import ABC, abstractmethod
from typing import List, Dict, Any
from src.core.domain.chunk import Chunk

class IVectorStore(ABC):
    @abstractmethod
    def upsert(self, collection_id: str, chunks: List[Chunk]) -> None:
        """Inserta fragmentos en una colección específica."""
        pass

    @abstractmethod
    def search(self, collection_id: str, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Busca fragmentos solo dentro de la colección indicada."""
        pass