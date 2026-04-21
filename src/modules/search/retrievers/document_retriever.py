from typing import List, Dict, Any
from src.core.ports.vector_store import IVectorStore
from src.core.ports.embedding_provider import IEmbeddingProvider
from src.core.ports.llm_client import ILLMClient
from .base import IRetriever

class DocumentRetriever(IRetriever):
    def __init__(self, vector_store: IVectorStore, embed_provider: IEmbeddingProvider, llm_client: ILLMClient):
        self.vector_store = vector_store
        self.embed_provider = embed_provider
        self.llm = llm_client

    async def retrieve(self, question: str, collection_id: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        # 1. Expansión de consulta
        expanded_query = question
        if params.get("requires_query_expansion", True):
            expanded_query = await self._expand_query(question)

        # 2. Vectorizar
        query_vector = self.embed_provider.embed_text(expanded_query)

        # 3. Búsqueda
        top_k = params.get("top_k", 15)
        results = self.vector_store.search(
            collection_id=collection_id,
            query_vector=query_vector,
            top_k=top_k,
            where=None
        )

        # 4. Compresión de contexto (opcional)
        if params.get("compress_context", False):
            compressed = await self._compress_context(question, results)
            # En este caso se devuelve un solo chunk artificial con el texto comprimido
            return [{"content": compressed, "metadata": {}}]

        return results

    async def _expand_query(self, question: str) -> str:
        prompt = f"""
Expande la siguiente pregunta en una consulta de búsqueda más completa y descriptiva,
manteniendo los términos clave y añadiendo sinónimos relevantes.
Pregunta: {question}
Consulta expandida:
"""
        return await self.llm.generate(prompt)

    async def _compress_context(self, question: str, chunks: List[Dict]) -> str:
        context_text = "\n\n".join([c["content"] for c in chunks])
        prompt = f"""
Extrae únicamente las oraciones del siguiente contexto que son directamente relevantes
para responder a la pregunta. No inventes información.

Pregunta: {question}
Contexto: {context_text}
Oraciones relevantes:
"""
        return await self.llm.generate(prompt)