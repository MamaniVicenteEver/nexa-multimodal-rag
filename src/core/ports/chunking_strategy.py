"""
Interfaz para estrategias de chunking.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from src.core.domain.chunk import Chunk


class IChunkingStrategy(ABC):
    """
    Puerto para dividir texto en chunks según una estrategia específica.
    """

    @abstractmethod
    def split(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        """
        Divide el texto en chunks.

        Args:
            text: Texto a dividir.
            metadata: Metadatos base para todos los chunks.

        Returns:
            Lista de objetos Chunk listos para ser embedidos.
        """
        pass