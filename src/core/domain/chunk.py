from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid

class Chunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    type: str = "text"
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)