from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from src.core.domain.collection_type import CollectionType

class IDatabaseRepository(ABC):
    @abstractmethod
    def create_collection(self, collection_id: str, name: str, description: Optional[str], collection_type: CollectionType) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_collections(self, skip: int, limit: int, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        pass
        
    @abstractmethod
    def get_collection_by_id(self, collection_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_document_record(self, doc_id: str, collection_id: str, filename: str) -> None:
        pass

    @abstractmethod
    def update_metrics(self, collection_id: str, doc_id: str, new_chunks: int) -> None:
        pass

    @abstractmethod
    def update_document_status(self, doc_id: str, status: str, error_message: Optional[str] = None) -> None:
        pass