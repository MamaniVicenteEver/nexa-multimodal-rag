from abc import ABC, abstractmethod

class ILLMClient(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Genera una respuesta de texto basada en un prompt."""
        pass