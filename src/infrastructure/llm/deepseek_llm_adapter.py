from openai import AsyncOpenAI
from typing import Optional, List, Dict, Any
from src.core.ports.llm_client import ILLMClient
from src.shared.config import settings
from src.shared.logging import get_logger

logger = get_logger("deepseek_llm_adapter")

class DeepSeekLLMAdapter(ILLMClient):
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            timeout=60.0
        )
        self.model = settings.DEEPSEEK_CHAT_MODEL

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 4096,
        messages: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Genera una respuesta usando el modelo DeepSeek.

        Args:
            prompt: Texto de la pregunta o instrucción del usuario.
            system_prompt: Instrucción de sistema (rol).
            temperature: Nivel de creatividad (0.0 = determinista, 2.0 = máximo).
            max_tokens: Longitud máxima de la respuesta.
            messages: Lista de mensajes predefinidos (ignora prompt y system_prompt si se proporciona).

        Returns:
            Respuesta generada por el modelo.
        """
        try:
            logger.info("Enviando prompt a DeepSeek LLM", extra={"model": self.model})

            # Construir mensajes
            if messages:
                # Usar directamente la lista de mensajes proporcionada
                formatted_messages = messages
            else:
                # Construir a partir de prompt y system_prompt
                sys_msg = system_prompt or "Eres un asistente especializado en análisis de documentos. Responde ÚNICAMENTE basándote en el contexto proporcionado."
                formatted_messages = [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": prompt},
                ]

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )

            logger.info("Respuesta recibida de DeepSeek LLM exitosamente")
            return response.choices[0].message.content

        except Exception as e:
            logger.error("Error al generar respuesta con DeepSeek LLM", exc_info=True)
            raise