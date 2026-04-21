"""
Fábrica para obtener la estrategia de chunking según el contrato.
"""

from src.core.ports.chunking_strategy import IChunkingStrategy
from src.infrastructure.chunking.entity_chunker import EntityChunker
from src.infrastructure.chunking.recursive_chunker import RecursiveChunker
from src.core.domain.collection_type import CollectionType
from src.shared.config import settings
from src.shared.logging import get_logger

logger = get_logger("chunking_factory")


def get_chunking_strategy(collection_type: CollectionType) -> IChunkingStrategy:
    """
    Devuelve la estrategia de chunking según el tipo solicitado.

    Args:
        strategy_type: 'simple' para catálogos, 'long' para documentos extensos.

    Returns:
        Instancia de IChunkingStrategy.
    """
    if collection_type == CollectionType.CATALOG:
        logger.info("Usando estrategia ENTITY CHUNKER (catálogos/productos)")
        return EntityChunker(
            min_chunk_size=getattr(settings, 'ENTITY_CHUNK_MIN_SIZE', 100),
            max_chunk_size=getattr(settings, 'ENTITY_CHUNK_MAX_SIZE', 2000)
        )
    elif collection_type == CollectionType.DOCUMENT:
        logger.info("Usando estrategia RECURSIVE CHUNKER (documentos largos)")
        return RecursiveChunker(
            chunk_size=getattr(settings, 'RECURSIVE_CHUNK_SIZE', 1000),
            chunk_overlap=getattr(settings, 'RECURSIVE_CHUNK_OVERLAP', 200)
        )
    else:
        raise ValueError(f"Estrategia de chunking desconocida: {collection_type}")