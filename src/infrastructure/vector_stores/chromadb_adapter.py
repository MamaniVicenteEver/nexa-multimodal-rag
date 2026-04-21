import os
import chromadb
from typing import List, Dict, Any
from src.core.domain.chunk import Chunk
from src.core.ports.vector_store import IVectorStore
from src.shared.config import settings
from src.shared.logging import get_logger
from typing import List, Dict, Any, Optional

logger = get_logger("chromadb_adapter")
class ChromaDBAdapter(IVectorStore):
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            os.makedirs(settings.CHROMA_PATH, exist_ok=True)
            self._client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
        return self._client

    def _get_or_create_collection(self, collection_id: str):
        """Obtiene o crea una colección aislada basada en el ID del proyecto."""
        client = self._get_client()
        # ChromaDB requiere nombres alfanuméricos válidos
        safe_name = f"col_{collection_id.replace('-', '_')}"
        return client.get_or_create_collection(name=safe_name)

    def upsert(self, collection_id: str, chunks: List[Chunk]) -> None:
        collection = self._get_or_create_collection(collection_id)
        
        ids = []
        documents = []
        embeddings = []
        metadatas = []
        
        for c in chunks:
            if c.embedding is None:
                logger.warning(f"Chunk {c.id} no tiene embedding, omitiendo")
                continue
            
            ids.append(c.id)
            documents.append(c.content)
            embeddings.append(c.embedding)
            
            meta = {
                "document_id": c.document_id,
                "type": c.type
            }
            if c.metadata:
                meta.update(c.metadata)
            metadatas.append(meta)
        
        if ids:
            collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            logger.info(f"Upsert completado: {len(ids)} chunks")
        else:
            logger.warning("No hay chunks válidos para insertar")

    def search(
        self,
        collection_id: str,
        query_vector: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Busca los vectores más similares en la colección.

        Args:
            collection_id: ID de la colección en ChromaDB.
            query_vector: Vector de la consulta.
            top_k: Número de resultados a devolver.
            where: Filtro de metadatos (ej. {"brand": "Adidas"}).
        """
        collection = self._get_or_create_collection(collection_id)
        
        query_params = {
            "query_embeddings": [query_vector],
            "n_results": top_k,
        }
        if where:
            query_params["where"] = where

        results = collection.query(**query_params)

        # Formatear resultados
        chunks = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                chunks.append({
                    "id": chunk_id,
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None
                })
        return chunks
