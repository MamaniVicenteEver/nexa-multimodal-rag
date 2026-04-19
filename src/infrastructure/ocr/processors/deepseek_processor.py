"""
Procesador para DeepSeek OCR 2 (página a página).

Utiliza DeepSeekOCRAdapter (existente) y extrae imágenes a partir de coordenadas.
"""

import asyncio
import os
import time
import io
from typing import List, Dict, Tuple

import fitz
from PIL import Image

from src.core.ports.page_processor import IPageProcessor
from src.infrastructure.ocr.deepseek_adapter import DeepSeekOCRAdapter, OCRMode
from src.infrastructure.ocr.processors.base import classify_page, extract_local, PageRoute
from src.shared.logging import get_logger

logger = get_logger("deepseek_processor")

IMAGES_DIR = os.path.join(os.getcwd(), "data", "extracted_images")
DEBUG_DIR = os.path.join(os.getcwd(), "data", "debug")
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)


def _rasterize_page_cpu(page: fitz.Page, dpi: int = 150) -> bytes:
    """Convierte página a JPEG para enviar a DeepSeek."""
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return pix.tobytes("jpeg", jpg_quality=85)


def _save_cropped_images(
    page: fitz.Page,
    bboxes: List[Tuple[int, int, int, int]],
    doc_id: str,
    page_num: int,
) -> List[str]:
    """Recorta y guarda imágenes a partir de coordenadas normalizadas (0-999)."""
    if not bboxes:
        return []

    pix = page.get_pixmap(dpi=150)
    img_data = pix.tobytes("png")
    full_img = Image.open(io.BytesIO(img_data))
    pw, ph = full_img.size
    urls = []

    for idx, (x1, y1, x2, y2) in enumerate(bboxes):
        left = int(x1 / 999 * pw)
        top = int(y1 / 999 * ph)
        right = int(x2 / 999 * pw)
        bottom = int(y2 / 999 * ph)
        left, right = min(left, right), max(left, right)
        top, bottom = min(top, bottom), max(top, bottom)

        cropped = full_img.crop((left, top, right, bottom))
        filename = f"{doc_id}_p{page_num+1}_img{idx}.png"
        path = os.path.join(IMAGES_DIR, filename)
        cropped.save(path)
        urls.append(f"/data/extracted_images/{filename}")
        logger.debug(f"Imagen guardada: {path}")

    return urls


class DeepSeekPageProcessor(IPageProcessor):
    """
    Procesador OCR basado en DeepSeek OCR 2.

    Procesa cada página individualmente, clasificándola primero para elegir
    el modo OCR adecuado (image, table, image_table).
    """

    def __init__(self):
        self.adapter = DeepSeekOCRAdapter()

    async def process_pages(
        self,
        pdf_bytes: bytes,
        page_indices: List[int],
        doc_id: str,
    ) -> Dict[int, Tuple[str, List[str]]]:
        """
        Procesa las páginas indicadas con DeepSeek.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        results: Dict[int, Tuple[str, List[str]]] = {}

        for idx in page_indices:
            page = doc[idx]
            route, mode, reason = classify_page(page)

            if route == PageRoute.LOCAL:
                # Aunque el orquestador ya habrá filtrado, manejamos el caso por si acaso
                logger.info(f"DeepSeek pág {idx+1}: clasificada LOCAL → PyMuPDF")
                results[idx] = (extract_local(page), [])
                continue

            # Rasterizar y llamar a DeepSeek
            img_bytes = await asyncio.to_thread(_rasterize_page_cpu, page, 150)
            ocr_mode_str = mode.value  # 'image', 'table', 'image_table'

            logger.info(f"DeepSeek pág {idx+1}: modo={ocr_mode_str} — {reason}")
            t0 = time.monotonic()

            ocr_result = await self.adapter.extract_once(img_bytes, mode=ocr_mode_str)

            elapsed = time.monotonic() - t0

            # Guardar raw para debug
            debug_path = os.path.join(DEBUG_DIR, f"{doc_id}_p{idx+1}_deepseek_raw.txt")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(ocr_result.raw)

            if not ocr_result.accepted:
                logger.warning(
                    f"DeepSeek pág {idx+1}: rechazado ({elapsed:.1f}s) → fallback PyMuPDF"
                )
                results[idx] = (extract_local(page), [])
            else:
                image_urls = _save_cropped_images(
                    page, ocr_result.image_coords, doc_id, idx
                )
                logger.info(
                    f"DeepSeek pág {idx+1}: OK — {len(ocr_result.clean):,} chars, "
                    f"{len(image_urls)} imágenes, {elapsed:.1f}s"
                )
                results[idx] = (ocr_result.clean, image_urls)

        doc.close()
        return results