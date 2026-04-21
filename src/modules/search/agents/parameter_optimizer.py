import json
from src.core.ports.llm_client import ILLMClient
from src.shared.logging import get_logger

logger = get_logger("param_optimizer")

class ParameterOptimizer:
    def __init__(self, llm_client: ILLMClient):
        self.llm = llm_client

    async def optimize(self, question: str, strategy: str, intent_hint: str = "") -> dict:
        """
        Retorna: {"top_k": int, "temperature": float, "apply_reranking": bool}
        """
        prompt = f"""
Eres un optimizador de parámetros de búsqueda RAG.
Contexto:
- Estrategia de búsqueda: {strategy} (simple=catálogo, long=documento largo)
- Pregunta: {question}
- Intención inferida: {intent_hint}

Devuelve JSON con los siguientes campos:
{{
  "top_k": número de candidatos a recuperar (3-20),
  "temperature": valor entre 0.0 y 1.0,
  "apply_reranking": true/false
}}
"""
        response = await self.llm.generate(prompt)
        try:
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            params = json.loads(response.strip())
        except json.JSONDecodeError:
            # Valores por defecto según estrategia
            if strategy == "simple":
                params = {"top_k": 10, "temperature": 0.3, "apply_reranking": True}
            else:
                params = {"top_k": 15, "temperature": 0.5, "apply_reranking": False}
        return params