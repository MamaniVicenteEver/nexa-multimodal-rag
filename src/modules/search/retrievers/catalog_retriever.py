from typing import List, Dict, Any
from src.core.ports.vector_store import IVectorStore
from src.core.ports.embedding_provider import IEmbeddingProvider
from src.infrastructure.vector_stores.chromadb_adapter import ChromaDBAdapter  # o interfaz\
from src.shared.config import settings
from .base import IRetriever

class CatalogRetriever(IRetriever):
    def __init__(self, vector_store: IVectorStore, embed_provider: IEmbeddingProvider):
        self.vector_store = vector_store
        self.embed_provider = embed_provider

    async def retrieve(self, question: str, collection_id: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        # 1. Extraer filtros (opcional: usar self-querying)
        filters = params.get("filters", {})

        # 2. Vectorizar pregunta
        query_vector = self.embed_provider.embed_text(question)

        results = self.vector_store.search(
            collection_id=collection_id,
            query_vector=query_vector,
            top_k=params.get("top_k", 20),
            where=filters if filters else None
        )

        # Filtrar por umbral de similitud
        threshold = getattr(settings, 'SIMILARITY_THRESHOLD', 0.5)
        filtered = [r for r in results if r.get("distance", 1.0) < threshold]

        # Si después del filtro no hay nada, devolvemos lista vacía
        if not filtered:
            return []

        # Aplicar reranking si es necesario (solo sobre los filtrados)
        if params.get("apply_reranking", False):
            filtered = await self.reranker.rerank(question, filtered, top_k=3)

        return filtered

    async def _rerank(self, question: str, chunks: List[Dict]) -> List[Dict]:
        # Implementación futura con BGE
        return chunks