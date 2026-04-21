from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

class ILLMClient(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 4096,
        messages: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Genera una respuesta a partir de un prompt o una lista de mensajes.

        Args:
            prompt: Texto principal de la consulta.
            system_prompt: Instrucción de sistema (opcional).
            temperature: Control de aleatoriedad (0.0 - 2.0).
            max_tokens: Límite de tokens en la respuesta.
            messages: Lista de mensajes con roles ('system', 'user', 'assistant').
                      Si se proporciona, ignora 'prompt' y 'system_prompt'.

        Returns:
            Texto generado por el modelo.
        """
        pass