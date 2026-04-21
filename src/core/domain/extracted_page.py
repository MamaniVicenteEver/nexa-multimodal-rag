"""
Representa una página procesada de un documento, con su contenido limpio
y metadatos asociados.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ExtractedPage:
    """Página extraída de un documento, lista para chunking."""

    page_number: int                     # Número de página (1‑based) para mostrar al usuario
    content: str                         # Texto Markdown limpio, sin cabeceras decorativas
    page_type: str                       # "LOCAL", "OCR", "TEXT" o "OMITIDA"
    image_urls: List[str] = field(default_factory=list)   # URLs de imágenes ya extraídas (si aplica)
    metadata: Dict[str, Any] = field(default_factory=dict) # Metadatos adicionales (ej. doc_id, page_index)