from abc import ABC, abstractmethod
from typing import List, Dict, Any

class IRetriever(ABC):
    @abstractmethod
    async def retrieve(self, question: str, collection_id: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Devuelve lista de chunks con su metadata"""
        pass