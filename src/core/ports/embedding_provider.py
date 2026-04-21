from abc import ABC, abstractmethod
from typing import List

class IEmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Convierte texto en un vector numérico."""
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Convierte una lista de textos en una lista de vectores numéricos."""
        pass