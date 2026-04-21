from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class QueryRequest(BaseModel):
    collection_id: str = Field(..., description="ID de la colección a consultar")
    question: str = Field(..., description="Pregunta del usuario")

class Source(BaseModel):
    content: str
    page_number: Optional[int] = None
    page_type: Optional[str] = None
    chunk_type: str = "text"
    image_url: Optional[str] = None
    gallery: Optional[List[str]] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]