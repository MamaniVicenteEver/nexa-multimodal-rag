from abc import ABC, abstractmethod

class IVisionProvider(ABC):
    @abstractmethod
    async def describe_image(self, image_url_or_path: str, context: str) -> str:
        """Genera una descripción semántica de una imagen dado su contexto."""
        pass