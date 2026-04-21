from google import genai
from typing import Optional, List, Dict, Any
from src.core.ports.llm_client import ILLMClient
from src.shared.config import settings
from src.shared.logging import get_logger

logger = get_logger("gemini_llm_adapter")

class GeminiLLMAdapter(ILLMClient):
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_CHAT_MODEL  # Ej: "gemini-3.1-flash-lite-preview"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 4096,
        messages: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Genera una respuesta usando el modelo Gemini.

        Args:
            prompt: Texto de la pregunta o instrucción del usuario.
            system_prompt: Instrucción de sistema (rol).
            temperature: Nivel de creatividad (0.0 = determinista, 2.0 = máximo).
            max_tokens: Longitud máxima de la respuesta (Gemini usa 'max_output_tokens').
            messages: Lista de mensajes predefinidos (ignora prompt y system_prompt si se proporciona).

        Returns:
            Respuesta generada por el modelo.
        """
        try:
            logger.info("Enviando prompt a Gemini LLM", extra={"model": self.model})

            # Construir contenido
            if messages:
                # Gemini espera un formato ligeramente distinto: convertir roles
                contents = []
                for msg in messages:
                    role = "user" if msg["role"] == "user" else "model"
                    contents.append({"role": role, "parts": [{"text": msg["content"]}]})
            else:
                sys_msg = system_prompt or "Eres un asistente especializado en análisis de documentos. Responde ÚNICAMENTE basándote en el contexto proporcionado."
                # Gemini no tiene un campo system_prompt separado en la API de chat; lo prependemos al mensaje del usuario
                full_prompt = f"{sys_msg}\n\n{prompt}"
                contents = [{"role": "user", "parts": [{"text": full_prompt}]}]

            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                }
            )

            logger.info("Respuesta recibida de Gemini LLM exitosamente")
            return response.text

        except Exception as e:
            logger.error("Error al generar respuesta con Gemini LLM", exc_info=True)
            raise