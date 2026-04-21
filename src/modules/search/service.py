import asyncio
from typing import Dict, Any, List

from src.core.ports.vector_store import IVectorStore
from src.core.ports.embedding_provider import IEmbeddingProvider
from src.core.ports.llm_client import ILLMClient
from src.core.ports.database_repository import IDatabaseRepository

from src.modules.search.agents.query_intake import QueryIntakeAgent
from src.modules.search.agents.parameter_optimizer import ParameterOptimizer
from src.modules.search.retrievers.catalog_retriever import CatalogRetriever
from src.modules.search.retrievers.document_retriever import DocumentRetriever

from src.shared.logging import get_logger

logger = get_logger("search_orchestrator")


class SearchOrchestrator:
    def __init__(
        self,
        vector_store: IVectorStore,
        embed_adapter: IEmbeddingProvider,
        llm_client: ILLMClient,
        db_adapter: IDatabaseRepository,
    ):
        self.vector_store = vector_store
        self.embed_adapter = embed_adapter
        self.llm_client = llm_client
        self.db_adapter = db_adapter

    async def execute(self, question: str, collection_id: str) -> Dict[str, Any]:
        # 1. Obtener metadatos de la colección
        collection = self.db_adapter.get_collection_by_id(collection_id)
        if not collection:
            raise ValueError(f"Colección no encontrada: {collection_id}")

        # 2. Leer el tipo de colección directamente (NUEVO)
        collection_type = collection.get("type")  # "catalog" o "document"
        logger.info(f"Procesando consulta para colección tipo '{collection_type}'")

        # 3. Seleccionar retriever según el tipo (NUEVO)
        if collection_type == "catalog":
            retriever = CatalogRetriever(self.vector_store, self.embed_adapter, self.llm_client)
        else:
            retriever = DocumentRetriever(self.vector_store, self.embed_adapter, self.llm_client)

        # 4. Definir parámetros fijos por tipo (NUEVO)
        params = {
            "top_k": 10,
            "temperature": 0.3,
            "apply_reranking": (collection_type == "catalog"),
        }

        # 5. Recuperar chunks
        chunks = await retriever.retrieve(question, collection_id, params)
        logger.info(f"Chunks recuperados: {len(chunks)}")

        # 6. Construir el prompt final (SIN CAMBIOS)
        if not chunks:
                return {
                    "answer": "Lo siento, no encontré información relevante en esta colección para tu consulta.",
                    "images_referenced": [],
                    "sources": []
                }

        context_parts = []
        image_urls = []
        for idx, chunk in enumerate(chunks):
            content = chunk.get("content", "")
            metadata = chunk.get("metadata", {})
            if metadata.get("type") == "image":
                url = metadata.get("image_url", "")
                if url:
                    image_urls.append(url)
                context_parts.append(f"[Fragmento {idx+1} - IMAGEN]: {content}")
            else:
                context_parts.append(f"[Fragmento {idx+1} - TEXTO]: {content}")

        full_context = "\n\n".join(context_parts)

        final_prompt = f"""
    Eres un asistente experto analizando documentos de una base de conocimiento.
    Utiliza ÚNICAMENTE la siguiente información para responder a la pregunta.
    Si la respuesta no está en el contexto, di "No tengo suficiente información en la colección consultada".

    --- CONTEXTO RECUPERADO ---
    {full_context}
    ---------------------------

    Pregunta: {question}
    """

        # 7. Generar respuesta final (SIN CAMBIOS)
        temperature = params.get("temperature", 0.3)
        answer = await self.llm_client.generate(
            prompt=final_prompt,
            system_prompt="Eres un asistente que responde preguntas basándose únicamente en el contexto proporcionado.",
            temperature=temperature
        )

        # 8. Formatear fuentes (SIN CAMBIOS)
        sources = []
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            chunk_type = meta.get("type", "text")
            source_info = {
                "content": chunk.get("content", ""),
                "page_number": meta.get("page_number"),
                "page_type": meta.get("page_type"),
                "chunk_type": chunk_type,
                "image_url": meta.get("image_url") if chunk_type in ("image", "entity") else None,
            }
            gallery = meta.get("gallery")
            if gallery and isinstance(gallery, list):
                source_info["gallery"] = gallery
            sources.append(source_info)

        return {
            "answer": answer,
            "images_referenced": list(set(image_urls)),
            "sources": sources
        }