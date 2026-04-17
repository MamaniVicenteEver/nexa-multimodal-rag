from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.core.ports.embedding_provider import IEmbeddingProvider
from src.core.ports.vector_store import IVectorStore
from src.core.ports.llm_client import ILLMClient
from src.shared.container import Container
from src.shared.logging import get_logger

router = APIRouter(prefix="/v1/query", tags=["Search"])
logger = get_logger("search_router")

class QueryRequest(BaseModel):
    question: str

@router.post("/")
async def search_query(
    request: QueryRequest,
    embed_adapter: IEmbeddingProvider = Depends(Container.get_embedding_provider),
    vector_store: IVectorStore = Depends(Container.get_vector_store),
    llm_adapter: ILLMClient = Depends(Container.get_llm_client)
):
    try:
        logger.info("Peticion de busqueda recibida", extra={"question": request.question})
        
        # 1. Vectorizar pregunta
        logger.debug("Iniciando vectorizacion de la pregunta...")
        query_vector = embed_adapter.embed_text(request.question)
        logger.info("Pregunta vectorizada con exito")
        
        # 2. Buscar en ChromaDB
        logger.debug("Buscando fragmentos en ChromaDB...")
        retrieved_chunks = vector_store.search(query_vector, top_k=5)
        logger.info("Busqueda en ChromaDB completada", extra={"chunks_retrieved": len(retrieved_chunks)})
        
        if not retrieved_chunks:
            logger.warning("No se encontraron fragmentos relevantes en la base de datos")
            return {"answer": "No se encontro informacion en los documentos."}

        # 3. Ensamblar Prompt
        context = "\n\n".join([c["content"] for c in retrieved_chunks])
        prompt = f"Contexto:\n{context}\n\nPregunta: {request.question}"
        
        # 4. Generar Respuesta
        logger.debug("Delegando generacion de respuesta final al LLM...")
        answer = await llm_adapter.generate(prompt)
        
        logger.info("Peticion de busqueda procesada y respondida exitosamente")
        return {
            "answer": answer,
            "sources": retrieved_chunks
        }
        
    except Exception as e:
        logger.error("Fallo durante el pipeline de busqueda", exc_info=True)
        # Esto será capturado por el global_exception_handler definido en main.py
        raise