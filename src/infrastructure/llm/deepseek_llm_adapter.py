from openai import AsyncOpenAI
from src.core.ports.llm_client import ILLMClient
from src.shared.config import settings
from src.shared.logging import get_logger

logger = get_logger("deepseek_llm_adapter")

class DeepSeekLLMAdapter(ILLMClient):
    def __init__(self):
        # Configuramos un timeout estricto para evitar bloqueos infinitos
        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY, 
            base_url=settings.DEEPSEEK_BASE_URL,
            timeout=60.0 
        )
        self.model = settings.DEEPSEEK_CHAT_MODEL

    async def generate(self, prompt: str) -> str:
        try:
            logger.info("Enviando prompt a DeepSeek LLM", extra={"model": self.model})
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a specialized document analysis assistant. Answer ONLY based on the provided context."},
                    {"role": "user", "content": prompt},
                ],
                stream=False
            )
            
            logger.info("Respuesta recibida de DeepSeek LLM exitosamente")
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("Error al generar respuesta con DeepSeek LLM", exc_info=True)
            raise