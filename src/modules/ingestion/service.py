import os
from src.core.domain.chunk import Chunk
from src.core.ports.ocr_provider import IOCRProvider
from src.core.ports.embedding_provider import IEmbeddingProvider
from src.core.ports.vector_store import IVectorStore
from src.core.ports.database_repository import IDatabaseRepository

from src.modules.ingestion.chunker import DocumentChunker
from src.modules.ingestion.hybrid_router import HybridDocumentProcessor
from src.shared.logging import get_logger

logger = get_logger("ingestion_service")
chunker = DocumentChunker()

async def process_document_task(
    doc_id: str, 
    collection_id: str,
    file_bytes: bytes,
    mime_type: str,
    original_filename: str,
    ocr_adapter: IOCRProvider,
    embed_adapter: IEmbeddingProvider,
    vector_store: IVectorStore,
    db_adapter: IDatabaseRepository
):
    try:
        # 0. Cambiamos estado en Base de Datos a PROCESANDO
        db_adapter.update_document_status(doc_id, "processing")
        
        # Extraer extensión para los logs
        _, file_extension = os.path.splitext(original_filename)
        logger.info(f"Iniciando procesamiento de documento", extra={
            "doc_id": doc_id, 
            "collection_id": collection_id, 
            "extension": file_extension or "Desconocida",
            "mime_type": mime_type
        })
        
        hybrid_processor = HybridDocumentProcessor(visual_ocr_adapter=ocr_adapter)
        
        # 1. Estrategia de Extracción
        if mime_type == "application/pdf":
            logger.info(f"Archivo PDF detectado ({file_extension}). Iniciando Enrutamiento Híbrido.")
            markdown_text = await hybrid_processor.process_pdf(file_bytes, doc_id)
            
        elif mime_type.startswith("image/"):
            logger.info(f"Imagen detectada ({file_extension}). Enviando directamente al OCR Visual.")
            markdown_text = await ocr_adapter.extract(file_bytes)
            
        elif mime_type.startswith("text/"):
            logger.info(f"Archivo de texto detectado ({file_extension}). Extracción directa y gratuita.")
            markdown_text = file_bytes.decode('utf-8', errors='ignore')
            
        else:
            raise ValueError(f"Formato no soportado: {mime_type}")
        
        # 2. Chunking Semántico
        text_chunks = chunker.split_text(markdown_text)
        total_chunks = len(text_chunks)
        logger.info("Chunking completado", extra={"total_chunks": total_chunks})
        
        # 3. Vectorización
        chunks_to_save = []
        for text in text_chunks:
            embedding = embed_adapter.embed_text(text)
            chunk = Chunk(document_id=doc_id, content=text, embedding=embedding)
            chunks_to_save.append(chunk)
            
        # 4. Persistencia Aislada en ChromaDB
        vector_store.upsert(collection_id, chunks_to_save)
        
        # 5. Actualizar Métricas y Estado FINAL a READY en PostgreSQL
        db_adapter.update_metrics(collection_id=collection_id, doc_id=doc_id, new_chunks=total_chunks)
        
        logger.info("Procesamiento en segundo plano FINALIZADO con éxito", extra={"doc_id": doc_id, "status": "ready"})
            
    except Exception as e:
        # 1. El log guarda el error, stacktrace, doc_id y collection_id en logs/error.log
        logger.error(
            "Fallo critico en el pipeline de ingesta", 
            exc_info=True, 
            extra={
                "doc_id": doc_id, 
                "collection_id": collection_id
            }
        )
        
        # 2. La base de datos SOLO actualiza el estado. Cero deuda técnica.
        db_adapter.update_document_status(doc_id, "failed")