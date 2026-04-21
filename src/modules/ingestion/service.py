"""
Servicio de ingesta de documentos - Versión refactorizada con estrategias de chunking
y metadatos de página en cada chunk.
"""

import os
from typing import List

from src.core.domain.chunk import Chunk
from src.core.ports.ocr_provider import IOCRProvider
from src.core.ports.embedding_provider import IEmbeddingProvider
from src.core.ports.vector_store import IVectorStore
from src.core.ports.database_repository import IDatabaseRepository
from src.core.ports.vision_provider import IVisionProvider

from src.modules.ingestion.hybrid_router import HybridDocumentProcessor
from src.modules.ingestion.chunker import DocumentChunker
from src.modules.ingestion.image_enricher import ImageEnricher
from src.modules.ingestion.normalizer import TextNormalizer
from src.modules.ingestion.document_extractor import DocumentExtractor
from src.core.domain.collection_type import CollectionType 
from src.shared.logging import get_logger
from src.infrastructure.chunking.factory import get_chunking_strategy

logger = get_logger("ingestion_service")
chunker = DocumentChunker()
normalizer = TextNormalizer()


async def process_document_task(
    doc_id: str,
    collection_id: str,
    file_bytes: bytes,
    mime_type: str,
    original_filename: str,
    ocr_adapter: IOCRProvider,
    embed_adapter: IEmbeddingProvider,
    vector_store: IVectorStore,
    db_adapter: IDatabaseRepository,
    vision_provider: IVisionProvider,
    collection_type: str,
):
    try:
        db_adapter.update_document_status(doc_id, "processing")
        _, file_extension = os.path.splitext(original_filename)

        col_type = CollectionType.from_string(collection_type)

        logger.info("Iniciando procesamiento de documento",
                    extra={"doc_id": doc_id, "strategy": col_type})

        # -------------------------------------------------------------
        # 1. EXTRACCIÓN DE PÁGINAS (limpia, sin cabeceras)
        # -------------------------------------------------------------
        extractor = DocumentExtractor(ocr_adapter=ocr_adapter)
        extracted_pages = await extractor.extract(
            file_bytes=file_bytes,
            mime_type=mime_type,
            filename=original_filename,
            doc_id=doc_id
        )

        # -------------------------------------------------------------
        # 2. PROCESAMIENTO PÁGINA POR PÁGINA
        # -------------------------------------------------------------
        all_chunks: List[Chunk] = []
        strategy = get_chunking_strategy(col_type)

        for page in extracted_pages:
            if not page.content:
                logger.debug(f"Página {page.page_number} omitida (vacía)")
                continue

            # Normalizar contenido
            clean_content = normalizer.normalize(page.content)

            # Enriquecimiento de imágenes (multimodal)
            enricher = ImageEnricher(vision_provider)
            enriched_content, image_chunks = await enricher.extract_and_process(
                clean_content,
                doc_id,
                page.page_number
            )

            # Metadatos base para esta página
            base_metadata = {
                "document_id": doc_id,
                "collection_id": collection_id,
                "source_filename": original_filename,
                "page_number": page.page_number,
                "page_type": page.page_type,
            }

            # Chunking del texto de esta página
            text_chunks = strategy.split(enriched_content, base_metadata)

            # Añadir metadatos de página a los chunks de imagen
            # (Si ya vienen con page_number desde el enricher, podemos simplemente actualizar
            # o mantener el que traen; por consistencia, actualizamos con todos los metadatos base)
            for img_chunk in image_chunks:
                img_chunk.metadata.update(base_metadata)

            all_chunks.extend(text_chunks)
            all_chunks.extend(image_chunks)
            logger.info(f"Página {page.page_number}: {len(text_chunks)} texto + {len(image_chunks)} imagen")

        total_chunks = len(all_chunks)
        logger.info(f"Chunking completado: {total_chunks} chunks totales")
        # -------------------------------------------------------------
        # 3. EMBEDDING Y PERSISTENCIA (SIEMPRE ACTIVO)
        # -------------------------------------------------------------
        # Extraer todos los contenidos
        texts = [chunk.content for chunk in all_chunks]

        # Generar todos los embeddings en una (o pocas) llamadas
        embeddings = embed_adapter.embed_batch(texts)

        # Asignar cada embedding a su chunk
        for chunk, emb in zip(all_chunks, embeddings):
            chunk.embedding = emb

        vector_store.upsert(collection_id, all_chunks)
        logger.info("Vectores guardados en ChromaDB")

        db_adapter.update_metrics(collection_id=collection_id, doc_id=doc_id, new_chunks=total_chunks)
        db_adapter.update_document_status(doc_id, "ready")
        logger.info("Procesamiento FINALIZADO con éxito", extra={"doc_id": doc_id})

    except Exception as e:
        logger.error("Fallo critico en el pipeline", exc_info=True, extra={"doc_id": doc_id})
        db_adapter.update_document_status(doc_id, "failed")