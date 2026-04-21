from src.core.ports.llm_client import ILLMClient
from src.shared.logging import get_logger

logger = get_logger("response_validator")

class ResponseValidator:
    def __init__(self, llm_client: ILLMClient):
        self.llm = llm_client

    async def validate(self, answer: str, context_chunks: list[str]) -> bool:
        """
        Verifica que la respuesta esté respaldada por el contexto.
        Retorna True si es válida, False si hay alucinaciones.
        """
        context_text = "\n\n".join(context_chunks)
        prompt = f"""
Eres un validador estricto de respuestas RAG.
Determina si la respuesta generada está completamente respaldada por el contexto proporcionado.

Contexto:
{context_text}

Respuesta generada:
{answer}

¿Cada afirmación en la respuesta está respaldada por el contexto?
Responde exclusivamente "SÍ" o "NO".
"""
        response = await self.llm.generate(prompt)
        return "SÍ" in response.upper()