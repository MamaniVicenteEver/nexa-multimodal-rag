import re
import json
from typing import List, Dict, Any, Optional
from src.core.domain.chunk import Chunk
from src.core.ports.chunking_strategy import IChunkingStrategy
from src.infrastructure.chunking.base import clean_whitespace, merge_small_chunks
from src.shared.logging import get_logger

logger = get_logger("entity_chunker")


class EntityChunker(IChunkingStrategy):
    def __init__(self, min_chunk_size: int = 100, max_chunk_size: int = 2000):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    def split(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        if not text:
            return []

        metadata = metadata or {}
        metadata["chunking_strategy"] = "entity"

        document_id = metadata.get("document_id")
        if not document_id:
            raise ValueError("metadata debe contener 'document_id'")

        if text.strip().startswith('[') or text.strip().startswith('{'):
            chunks = self._split_json_like(text, metadata, document_id)
        else:
            chunks = self._split_by_separators(text, metadata, document_id)

        logger.info(f"EntityChunker: generados {len(chunks)} chunks")
        return chunks

    def _split_json_like(self, text: str, base_metadata: Dict, document_id: str) -> List[Chunk]:
        chunks = []
        try:
            data = json.loads(text)
            if isinstance(data, list):
                for idx, item in enumerate(data):
                    chunk_text = self._item_to_text(item)
                    if chunk_text:
                        meta = base_metadata.copy()
                        meta["entity_index"] = idx
                        chunks.append(self._create_chunk(chunk_text, meta, document_id, item))
            elif isinstance(data, dict):
                chunk_text = self._item_to_text(data)
                if chunk_text:
                    chunks.append(self._create_chunk(chunk_text, base_metadata, document_id, data))
        except json.JSONDecodeError:
            chunks = self._split_by_separators(text, base_metadata, document_id)
        return chunks

    def _split_by_separators(self, text: str, base_metadata: Dict, document_id: str) -> List[Chunk]:
        raw_chunks = re.split(r'\n\s*---+\s*\n|\n\s*\*\s*\*\s*\*\s*\n|\n{3,}', text)
        cleaned = [clean_whitespace(c) for c in raw_chunks if c.strip()]
        merged = merge_small_chunks(cleaned, self.min_chunk_size)

        chunks = []
        for idx, content in enumerate(merged):
            meta = base_metadata.copy()
            meta["entity_index"] = idx
            chunks.append(self._create_chunk(content, meta, document_id))
        return chunks

    def _item_to_text(self, item: Any) -> str:
        if isinstance(item, dict):
            # Excluir campos de imágenes para no llenar el texto del chunk con URLs largas
            exclude_keys = {"main_image", "images", "metadata"}
            parts = []
            for k, v in item.items():
                if k in exclude_keys:
                    continue
                if isinstance(v, (str, int, float)):
                    parts.append(f"{k}: {v}")
                elif isinstance(v, list):
                    parts.append(f"{k}: {', '.join(str(x) for x in v)}")
            return " | ".join(parts)
        elif isinstance(item, list):
            return " | ".join(str(x) for x in item)
        else:
            return str(item)

    def _create_chunk(self, content: str, metadata: Dict, document_id: str, item: Optional[Dict] = None) -> Chunk:
        if item and isinstance(item, dict):
            main_image = item.get("main_image")
            if main_image:
                metadata["image_url"] = main_image
            
            # Solo agregar gallery si la lista existe y tiene elementos
            gallery = item.get("images")
            if gallery and isinstance(gallery, list) and len(gallery) > 0:
                metadata["gallery"] = gallery
            
            if "sku" in item:
                metadata["sku"] = item["sku"]
            if "price" in item:
                metadata["price"] = item["price"]

        if len(content) > self.max_chunk_size:
            content = content[:self.max_chunk_size] + "..."

        return Chunk(
            document_id=document_id,
            content=content,
            metadata=metadata,
            type="entity"
        )