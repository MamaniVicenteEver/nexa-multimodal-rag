from abc import ABC, abstractmethod
from typing import List

class IEmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Convierte texto en un vector numérico."""
        pass