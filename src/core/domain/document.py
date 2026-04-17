from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone

class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"

class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    collection_id: str
    original_filename: str = ""
    status: DocumentStatus = DocumentStatus.PENDING
    pages: int = 0
    chunks_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)