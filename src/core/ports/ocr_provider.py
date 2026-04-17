from abc import ABC, abstractmethod

class IOCRProvider(ABC):
    @abstractmethod
    async def extract(self, file_bytes: bytes) -> str:
        """Extrae texto estructurado (Markdown) de un archivo binario."""
        pass