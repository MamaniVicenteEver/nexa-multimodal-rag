from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, Depends
from typing import Optional
import uuid

from src.core.ports.ocr_provider import IOCRProvider
from src.core.ports.embedding_provider import IEmbeddingProvider
from src.core.ports.vector_store import IVectorStore
from src.core.ports.file_storage import IFileStorage
from src.core.ports.database_repository import IDatabaseRepository

from src.shared.container import Container
from src.shared.logging import get_logger
from src.modules.ingestion.service import process_document_task

router = APIRouter(prefix="/v1/ingest", tags=["Ingestion"])
logger = get_logger("ingestion_router")

@router.post("/")
async def ingest_document(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...),
    collection_id: Optional[str] = Form(None, description="ID de la colección. Si se omite, se crea una nueva."),
    collection_name: Optional[str] = Form(None, description="Nombre de la nueva colección"),
    collection_description: Optional[str] = Form(None, description="Descripción o propósito del proyecto"),
    ocr_adapter: IOCRProvider = Depends(Container.get_ocr_provider),
    embed_adapter: IEmbeddingProvider = Depends(Container.get_embedding_provider),
    vector_store: IVectorStore = Depends(Container.get_vector_store),
    storage_adapter: IFileStorage = Depends(Container.get_storage_provider),
    db_adapter: IDatabaseRepository = Depends(Container.get_database_repository)
):
    doc_id = str(uuid.uuid4())
    
    # 1. Gestión de Colecciones
    if not collection_id:
        collection_id = str(uuid.uuid4())
        name = collection_name or f"Colección {collection_id[:8]}"
        db_adapter.create_collection(collection_id, name, collection_description)
        logger.info(f"Nueva colección creada: {collection_id}")
    else:
        exists = db_adapter.get_collection_by_id(collection_id)
        if not exists:
            # Usamos el nuevo formato de error manualmente para validaciones de negocio previas
            return {"error": True, "codigo": "COLLECTION_NOT_FOUND", "message": "La colección especificada no existe en la base de datos."}

    # 2. Registrar Documento en 'pending'
    db_adapter.save_document_record(doc_id, collection_id, file.filename)

    # 3. Guardar Físicamente
    file_bytes = await file.read()
    saved_path = await storage_adapter.save_file(file_bytes, f"{doc_id}_{file.filename}")
    logger.info("Archivo guardado en almacenamiento", extra={"path": saved_path})

    # 4. Delegar al Background Task
    logger.info("Delegando procesamiento en segundo plano...")
    background_tasks.add_task(
        process_document_task, 
        doc_id,
        collection_id,
        file_bytes, 
        file.content_type, 
        file.filename, # <-- Pasamos el nombre para saber la extensión
        ocr_adapter, 
        embed_adapter, 
        vector_store,
        db_adapter
    )
    
    # Respuesta Inmediata y Clara al Usuario
    return {
        "success": True,
        "document_id": doc_id, 
        "collection_id": collection_id,
        "status": "pending",
        "message": "El documento ha sido recibido y el procesamiento en segundo plano ha comenzado. Utilice el document_id para consultar el estado."
    }