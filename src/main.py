import os
from fastapi import FastAPI
from src.shared.config import settings
from src.shared.logging import get_logger
from src.shared.error_handlers import setup_exception_handlers

# Routers
from src.modules.ingestion.router import router as ingestion_router
from src.modules.search.router import router as search_router
from src.modules.collections.router import router as collections_router

# Base de datos
from src.infrastructure.database.models import init_db

logger = get_logger("fastapi_app")

def initialize_database():
    """
    Intenta inicializar la base de datos PostgreSQL.
    Si falla, la aplicación no se cae. Loguea el error en inglés y
    deja el camino preparado para un mecanismo de reintento.
    """
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"DATABASE_CONNECTION_FAILED: {str(e)}", exc_info=True)
        
        # TODO: Implement mitigation plan (e.g., Llama3-style backoff retry 3 times)
        # def retry_db_connection(retries=3, delay_seconds=5):
        #    ... lógica de reconexión futura ...
        # pass

# Arrancamos la DB antes de instanciar la App
initialize_database()

app = FastAPI(
    title="Nexa Multimodal RAG", 
    version="1.0.0",
    description="Motor RAG Multi-tenant basado en Arquitectura Hexagonal"
)

# Delegamos el manejo de errores (SRP)
setup_exception_handlers(app)

@app.get("/health", tags=["Admin"])
async def health_check():
    logger.info("Health check ejecutado")
    return {"status": "ok", "role": settings.NEXA_ROLE}

# Registro de Módulos
app.include_router(collections_router)
app.include_router(ingestion_router)
app.include_router(search_router)

def start_api():
    import uvicorn
    logger.info("Iniciando API de Nexa...")
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    start_api()