import json
from src.core.ports.llm_client import ILLMClient
from src.shared.logging import get_logger

logger = get_logger("query_intake")

class QueryIntakeAgent:
    def __init__(self, llm_client: ILLMClient):
        self.llm = llm_client

    async def decide(self, question: str, collection_info: dict) -> dict:
        """
        collection_info: {"name": ..., "description": ..., "strategy": "simple"|"long"}
        Retorna: {"effective_strategy": ..., "requires_self_querying": bool, "requires_query_expansion": bool, "reasoning": str}
        """
        prompt = f"""
            Eres un enrutador inteligente para un sistema RAG.
            Analiza la pregunta del usuario y la información de la colección.

            Colección: {collection.name} - {collection.description}
            Estrategia predefinida: {collection.strategy}  # 'catalog' o 'document'

            Pregunta: {question}

            Devuelve un JSON con:
            {{
            "effective_strategy": "catalog" | "document",
            "requires_self_querying": true/false,
            "suggested_filters": {{"brand": "Adidas", "category": "Tenis"}} (solo si catalog),
            "reasoning": "breve explicación"
            }}
            """
        response = await self.llm.generate(prompt)
        try:
            # Limpiar respuesta del LLM
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            decision = json.loads(response.strip())
        except json.JSONDecodeError:
            logger.warning("Fallback a estrategia por defecto")
            decision = {
                "effective_strategy": collection_info.get("strategy", "long"),
                "requires_self_querying": False,
                "requires_query_expansion": False,
                "reasoning": "fallback"
            }
        return decision