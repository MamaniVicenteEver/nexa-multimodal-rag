import os
import chromadb
from typing import List, Dict, Any
from src.core.domain.chunk import Chunk
from src.core.ports.vector_store import IVectorStore
from src.shared.config import settings

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
        
        ids = [c.id for c in chunks]
        documents = [c.content for c in chunks]
        embeddings = [c.embedding for c in chunks]
        metadatas = [{"document_id": c.document_id, "type": c.type} for c in chunks]
        
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

    def search(self, collection_id: str, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        collection = self._get_or_create_collection(collection_id)
        
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k
        )
        
        chunks_data = []
        if results['documents'] and len(results['documents'][0]) > 0:
            for i in range(len(results['documents'][0])):
                chunks_data.append({
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i]
                })
        return chunks_data