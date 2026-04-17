from fastapi import APIRouter, Depends, Query
from typing import Optional
from src.core.ports.database_repository import IDatabaseRepository
from src.shared.container import Container

router = APIRouter(prefix="/v1/collections", tags=["Collections"])

@router.get("/")
async def list_collections(
    skip: int = Query(0, description="Registros a omitir para paginacion"),
    limit: int = Query(10, description="Límite de registros por pagina"),
    start_date: Optional[str] = Query(None, description="Filtrar desde fecha (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filtrar hasta fecha (YYYY-MM-DD)"),
    db_adapter: IDatabaseRepository = Depends(Container.get_database_repository)
):
    """Devuelve todas las colecciones con sus métricas (Documentos, Chunks)."""
    collections = db_adapter.get_collections(skip, limit, start_date, end_date)
    return {
        "count": len(collections),
        "skip": skip,
        "limit": limit,
        "data": collections
    }