"""
Procesador para Mistral OCR.

Utiliza MistralOCRAdapter (existente) y enriquece el Markdown con tablas
extraídas del JSON crudo.
"""

import json
import os
import re
from typing import List, Dict, Tuple

from src.core.ports.page_processor import IPageProcessor
from src.infrastructure.ocr.mistral_adapter import MistralOCRAdapter
from src.infrastructure.ocr.processors.base import extract_local, OCRMode
from src.shared.logging import get_logger

logger = get_logger("mistral_processor")
DEBUG_DIR = os.path.join(os.getcwd(), "data", "debug")


class MistralPageProcessor(IPageProcessor):
    """
    Procesador OCR basado en Mistral (mistral-ocr-latest).

    Envía el PDF completo en una sola llamada, procesando solo las páginas indicadas.
    Las tablas se incrustan directamente en el Markdown.
    """

    def __init__(self):
        self.adapter = MistralOCRAdapter()

    async def process_pages(
        self,
        pdf_bytes: bytes,
        page_indices: List[int],
        doc_id: str,
    ) -> Dict[int, Tuple[str, List[str]]]:
        """
        Delega en MistralOCRAdapter y enriquece el resultado con tablas.
        """
        if not page_indices:
            return {}

        # Llamada al adaptador existente
        batch_result = await self.adapter.process_pdf_pages(
            pdf_bytes=pdf_bytes,
            page_indices=page_indices,
            doc_id=doc_id,
        )

        # Cargar JSON crudo para extraer tablas (guardado por el adaptador)
        raw_json_path = os.path.join(DEBUG_DIR, f"{doc_id}_mistral_raw.json")
        page_data_map = {}
        try:
            with open(raw_json_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            for p in raw_data.get("pages", []):
                page_data_map[p["index"]] = p
        except FileNotFoundError:
            logger.warning(f"No se encontró {raw_json_path}. Las tablas no se incrustarán.")

        results: Dict[int, Tuple[str, List[str]]] = {}

        for page_idx, page_result in batch_result.pages.items():
            markdown = page_result.markdown
            image_urls = page_result.image_urls

            # Incrustar tablas si existen
            page_data = page_data_map.get(page_idx)
            if page_data and "tables" in page_data:
                for table in page_data["tables"]:
                    table_content = table.get("content", "")
                    table_id = table.get("id", "")
                    if table_content and table_id:
                        placeholder = f"[{table_id}]({table_id})"
                        markdown = markdown.replace(placeholder, f"\n\n{table_content}\n\n")
                        logger.debug(f"Tabla {table_id} incrustada en pág {page_idx+1}")

            if page_result.accepted and markdown:
                results[page_idx] = (markdown, image_urls)
            else:
                # Fallback a local si Mistral falló
                logger.warning(f"Mistral pág {page_idx+1} no aceptada → fallback PyMuPDF")
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                fallback_md = extract_local(doc[page_idx])
                doc.close()
                results[page_idx] = (fallback_md, [])

        # Asegurar que todas las páginas solicitadas tengan entrada
        for idx in page_indices:
            if idx not in results:
                logger.warning(f"Mistral no devolvió pág {idx+1} → fallback PyMuPDF")
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                results[idx] = (extract_local(doc[idx]), [])
                doc.close()

        return results