"""
Procesador local (PyMuPDF) para páginas que no requieren OCR.

Implementa IPageProcessor.
"""

import fitz
from typing import List, Dict, Tuple

from src.core.ports.page_processor import IPageProcessor
from src.infrastructure.ocr.processors.base import extract_local
from src.shared.logging import get_logger

logger = get_logger("local_processor")


class LocalPageProcessor(IPageProcessor):
    """
    Procesador gratuito que usa PyMuPDF directamente.

    No realiza llamadas a APIs externas.
    """

    async def process_pages(
        self,
        pdf_bytes: bytes,
        page_indices: List[int],
        doc_id: str,
    ) -> Dict[int, Tuple[str, List[str]]]:
        """
        Procesa cada página con extract_local() y devuelve el Markdown.
        Las imágenes no se extraen (lista vacía).
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        results = {}

        for idx in page_indices:
            try:
                page = doc[idx]
                markdown = extract_local(page)
                results[idx] = (markdown, [])
                logger.debug(f"Local pág {idx+1}: {len(markdown)} chars")
            except Exception as e:
                logger.error(f"Error en página local {idx+1}: {e}")
                results[idx] = ("", [])

        doc.close()
        return results