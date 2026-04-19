"""
Orquestador híbrido para procesamiento de PDFs.

Versión simplificada que delega en un IPageProcessor.

Flujo:
  1. Abre el PDF y clasifica cada página.
  2. Separa índices LOCAL y OCR.
  3. Procesa LOCAL con extract_local().
  4. Procesa OCR delegando en self.page_processor.
  5. Ensambla Markdown final.
"""

import fitz
import os
import time
from typing import List, Tuple, Dict

from src.core.ports.page_processor import IPageProcessor
from src.infrastructure.ocr.processors.base import (
    classify_page,
    is_page_meaningful,
    extract_local,
    PageRoute,
)
from src.shared.logging import get_logger

logger = get_logger("hybrid_router")

DEBUG_DIR = os.path.join(os.getcwd(), "data", "debug")
os.makedirs(DEBUG_DIR, exist_ok=True)


class HybridDocumentProcessor:
    """
    Orquestador de extracción de PDFs.

    Recibe un IPageProcessor que sabe cómo manejar las páginas OCR.
    """

    def __init__(self, page_processor: IPageProcessor):
        self.page_processor = page_processor

    async def process_pdf(self, pdf_bytes: bytes, doc_id: str) -> str:
        """
        Procesa un PDF completo y devuelve un único Markdown.
        """
        t_start = time.monotonic()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)

        logger.info(f"INICIO procesamiento PDF — doc_id={doc_id}, páginas={total_pages}")

        # FASE 1: Clasificación local de todas las páginas
        local_indices: List[int] = []
        ocr_indices: List[int] = []
        skipped = 0

        for pnum in range(total_pages):
            page = doc[pnum]
            text = page.get_text("text").strip()

            if not is_page_meaningful(page, text):
                logger.info(f"Pág {pnum+1}: OMITIDA (vacía)")
                skipped += 1
                continue

            route, _, reason = classify_page(page)
            logger.info(f"Pág {pnum+1}: {route.upper()} ← {reason}")

            if route == PageRoute.LOCAL:
                local_indices.append(pnum)
            else:
                ocr_indices.append(pnum)

        logger.info(
            f"Clasificación: LOCAL={len(local_indices)}, OCR={len(ocr_indices)}, OMITIDAS={skipped}"
        )

        # FASE 2: Procesamiento
        page_results: Dict[int, Tuple[str, List[str]]] = {}

        # 2a. Páginas locales (gratis)
        for idx in local_indices:
            page = doc[idx]
            page_results[idx] = (extract_local(page), [])

        # 2b. Páginas OCR (delegar en el procesador inyectado)
        if ocr_indices:
            logger.info(f"Delegando {len(ocr_indices)} páginas OCR a {self.page_processor.__class__.__name__}")
            ocr_results = await self.page_processor.process_pages(
                pdf_bytes=pdf_bytes,
                page_indices=ocr_indices,
                doc_id=doc_id,
            )
            page_results.update(ocr_results)
        else:
            logger.info("Sin páginas OCR. No se llama a la API.")

        # FASE 3: Ensamblado final (en orden de página)
        parts = []
        for pnum in range(total_pages):
            if pnum in page_results:
                md, urls = page_results[pnum]
                header = f"\n\n{'='*40}\n📄 PÁGINA {pnum+1}\n{'='*40}\n\n"
                img_section = ""
                if urls and "deepseek" in self.page_processor.__class__.__name__.lower():
                    # Para DeepSeek añadimos sección de imágenes (Mistral ya las tiene incrustadas)
                    img_section = "\n\n**Imágenes extraídas:**\n" + "\n".join(
                        f"![Imagen]({url})" for url in urls
                    )
                parts.append(header + md + img_section)
            else:
                # Página omitida o no procesada
                parts.append(f"\n\n{'='*40}\n📄 PÁGINA {pnum+1} [OMITIDA]\n{'='*40}\n\n")

        doc.close()
        final_md = "".join(parts)

        # Guardar debug final
        debug_path = os.path.join(DEBUG_DIR, f"{doc_id}_final.md")
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(final_md)

        t_total = time.monotonic() - t_start
        logger.info(
            f"FIN procesamiento — doc_id={doc_id}, páginas_procesadas={len(page_results)}, "
            f"omitidas={skipped}, chars={len(final_md):,}, tiempo={t_total:.1f}s"
        )
        return final_md