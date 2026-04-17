from abc import ABC, abstractmethod

class IFileStorage(ABC):
    @abstractmethod
    async def save_file(self, file_bytes: bytes, filename: str) -> str:
        """Guarda un archivo y retorna la URL o ruta local."""
        pass