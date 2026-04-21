"""
Estrategia CONTRACT_LONG: división recursiva con solapamiento.
"""

from typing import List, Dict, Any, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.core.domain.chunk import Chunk
from src.core.ports.chunking_strategy import IChunkingStrategy
from src.infrastructure.chunking.base import clean_whitespace
from src.shared.logging import get_logger

logger = get_logger("recursive_chunker")


class RecursiveChunker(IChunkingStrategy):
    """
    Divide texto preservando la estructura semántica (párrafos, oraciones).
    Usa RecursiveCharacterTextSplitter de LangChain con overlap.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def split(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        if not text:
            return []

        metadata = metadata or {}
        metadata["chunking_strategy"] = "recursive"

        # Obtener document_id de los metadatos (obligatorio)
        document_id = metadata.get("document_id")
        if not document_id:
            raise ValueError("metadata debe contener 'document_id'")

        # Limpiar espacios excesivos pero mantener saltos de línea
        text = clean_whitespace(text)

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators,
            length_function=len,
            is_separator_regex=False,
        )

        docs = splitter.create_documents([text])
        chunks = []
        for i, doc in enumerate(docs):
            meta = metadata.copy()
            meta["chunk_index"] = i
            chunks.append(Chunk(
                document_id=document_id,          # <-- CAMPO OBLIGATORIO
                content=doc.page_content,
                metadata=meta,
                type="text"
            ))

        logger.info(f"RecursiveChunker: {len(text)} chars -> {len(chunks)} chunks (size={self.chunk_size}, overlap={self.chunk_overlap})")
        return chunks