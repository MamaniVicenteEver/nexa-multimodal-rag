from fastapi import APIRouter, Depends
from src.shared.container import Container
from src.modules.search.schemas import QueryRequest, QueryResponse
from src.modules.search.service import SearchOrchestrator

router = APIRouter(prefix="/v1/query", tags=["Search"])

@router.post("/", response_model=QueryResponse)
async def search_query(
    request: QueryRequest,
    orchestrator: SearchOrchestrator = Depends(Container.get_search_orchestrator)
):
    return await orchestrator.execute(request.question, request.collection_id)