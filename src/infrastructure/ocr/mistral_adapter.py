"""
src/infrastructure/ocr/mistral_adapter.py

Adaptador para Mistral OCR (mistral-ocr-latest).

DIFERENCIA CLAVE vs DeepSeek:
  - Acepta el PDF completo directamente (no página a página)
  - Cobra POR PÁGINA procesada → solo enviamos las páginas que necesitan OCR
  - Devuelve Markdown + imágenes en base64 + tablas en JSON por página
  - La API extrae las imágenes internamente → no necesitamos rasterizar ni recortar

MEJORAS IMPLEMENTADAS:
  - Extrae tablas del campo 'tables[0].content' y las incrusta directamente en el markdown
  - Guarda imágenes con extensión correcta (jpeg/png según el base64)
  - Reemplaza referencias de imágenes y tablas en el markdown final
  - Guarda respuesta cruda para depuración (opcional)
"""

import base64
import os
import time
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx
from src.shared.config import settings
from src.shared.logging import get_logger

logger = get_logger("mistral_ocr")

IMAGES_DIR = os.path.join(os.getcwd(), "data", "extracted_images")
DEBUG_DIR  = os.path.join(os.getcwd(), "data", "debug")
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(DEBUG_DIR,  exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# TIPOS DE RESULTADO
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class MistralPageResult:
    """Resultado OCR de una página procesada por Mistral."""
    page_index: int          # índice 0-based de la página en el PDF original
    markdown:   str          # Markdown limpio con tablas e imágenes incrustadas
    image_urls: list[str] = field(default_factory=list)  # URLs locales de imágenes guardadas
    accepted:   bool = True  # False si la página falló o devolvió nada útil


@dataclass
class MistralBatchResult:
    """Resultado completo de un lote de páginas enviado a Mistral."""
    pages:        dict[int, MistralPageResult]  # {page_index: result}
    pages_sent:   int   = 0
    pages_ok:     int   = 0
    pages_failed: int   = 0
    duration_sec: float = 0.0
    model:        str   = settings.MISTRAL_OCR_MODEL


# ──────────────────────────────────────────────────────────────────────────────
# GUARDADO DE IMÁGENES DESDE BASE64
# ──────────────────────────────────────────────────────────────────────────────

def _save_mistral_image(base64_data: str, doc_id: str, page_index: int, img_id: str) -> Optional[str]:
    """
    Guarda una imagen recibida en base64 (data:image/...;base64,xxx) como archivo.
    Detecta automáticamente la extensión (jpeg/png) y devuelve la URL relativa.
    """
    # Extraer el tipo de imagen y el base64 puro
    match = re.match(r'data:image/(\w+);base64,(.+)', base64_data)
    if not match:
        logger.warning(f"No se pudo extraer el tipo de imagen para {img_id}")
        return None
    
    img_type = match.group(1).lower()  # 'jpeg', 'png', etc.
    img_b64 = match.group(2)
    
    # Extensión correcta
    ext = 'jpg' if img_type == 'jpeg' else img_type
    
    try:
        img_bytes = base64.b64decode(img_b64)
        img_filename = f"{doc_id}_p{page_index+1}_{img_id}"
        # Asegurar extensión correcta (si el id ya tiene .jpeg, reemplazar)
        if '.' in img_filename:
            img_filename = img_filename.rsplit('.', 1)[0]
        img_filename = f"{img_filename}.{ext}"
        img_path = os.path.join(IMAGES_DIR, img_filename)
        
        with open(img_path, "wb") as f:
            f.write(img_bytes)
        
        logger.debug(f"Imagen guardada: {img_path} ({len(img_bytes):,} bytes, tipo={img_type})")
        return f"/data/extracted_images/{img_filename}"
    
    except Exception as e:
        logger.error(f"Error guardando imagen {img_id}: {e}")
        return None


def _replace_image_refs(markdown: str, image_url_map: dict) -> str:
    """
    Reemplaza las referencias de imagen en el markdown (ej. ![img-0.jpeg](img-0.jpeg))
    por las URLs locales reales.
    """
    result = markdown
    for img_id, url in image_url_map.items():
        # Busca ![nombre](img_id) y reemplaza por ![nombre](url)
        # Patrón que captura el alt text y el id exacto
        pattern = rf'!\[([^\]]*)\]\({re.escape(img_id)}\)'
        result = re.sub(pattern, rf'![\1]({url})', result)
    return result


# ──────────────────────────────────────────────────────────────────────────────
# ADAPTADOR PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────

class MistralOCRAdapter:
    """
    Adaptador para Mistral OCR (mistral-ocr-latest).

    Uso principal:
        result = await adapter.process_pdf_pages(
            pdf_bytes=<bytes del PDF completo>,
            page_indices=[0, 2],  # solo las que necesitan OCR
            doc_id="uuid-del-documento",
        )
    """

    def __init__(self):
        self.api_key  = settings.MISTRAL_API_KEY
        self.endpoint = settings.MISTRAL_OCR_ENDPOINT
        self.model    = settings.MISTRAL_OCR_MODEL

        if not self.api_key:
            logger.warning("MISTRAL_API_KEY no configurada.")

    async def process_pdf_pages(
        self,
        pdf_bytes:    bytes,
        page_indices: list[int],
        doc_id:       str,
        image_limit:  int | None = 20,
        image_min_size: int | None = 100,
    ) -> MistralBatchResult:
        """
        Envía el PDF completo a Mistral y procesa solo las páginas indicadas.
        Devuelve Markdown con tablas incrustadas y URLs de imágenes locales.
        """
        if not page_indices:
            logger.info("Mistral: no hay páginas para procesar")
            return MistralBatchResult(pages={})

        start_time = time.monotonic()
        logger.info(f"Mistral OCR — enviando PDF, procesando {len(page_indices)} páginas: {page_indices}")

        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        payload = {
            "model":    self.model,
            "document": {
                "type":          "document_url",
                "document_url":  f"data:application/pdf;base64,{pdf_b64}",
            },
            "pages":               page_indices,
            "include_image_base64": True,   # Necesitamos las imágenes
        }

        if image_limit is not None:
            payload["image_limit"] = image_limit
        if image_min_size is not None:
            payload["image_min_size"] = image_min_size

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                logger.info("Mistral: enviando request...")
                response = await client.post(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )

            if response.status_code != 200:
                logger.error(f"Mistral API error {response.status_code}: {response.text[:500]}")
                return MistralBatchResult(pages={}, pages_sent=len(page_indices), pages_failed=len(page_indices))

            data = response.json()
            logger.debug(f"Mistral respuesta OK. Modelo: {data.get('model')}")

        except Exception as e:
            logger.error(f"Mistral error: {e}")
            return MistralBatchResult(pages={}, pages_sent=len(page_indices), pages_failed=len(page_indices))

        # Guardar respuesta cruda para depuración (puedes comentar después)
        debug_path = os.path.join(DEBUG_DIR, f"{doc_id}_mistral_raw.json")
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Respuesta cruda guardada en {debug_path}")

        results: dict[int, MistralPageResult] = {}
        pages_ok = 0
        pages_ko = 0

        for page_data in data.get("pages", []):
            page_idx = page_data.get("index")
            markdown = page_data.get("markdown", "")
            
            # ─────────────────────────────────────────────────────────────────
            # 1. Extraer y guardar imágenes, construir mapa de reemplazo
            # ─────────────────────────────────────────────────────────────────
            image_url_map = {}
            for img in page_data.get("images", []):
                img_id = img.get("id")
                img_b64 = img.get("image_base64")
                if img_id and img_b64:
                    url = _save_mistral_image(img_b64, doc_id, page_idx, img_id)
                    if url:
                        image_url_map[img_id] = url
            
            # ─────────────────────────────────────────────────────────────────
            # 2. Extraer tablas del campo 'tables' y reemplazar [tbl-*.md]
            # ─────────────────────────────────────────────────────────────────
            for table in page_data.get("tables", []):
                table_id = table.get("id")      # ej: "tbl-0.md"
                table_content = table.get("content", "")
                if table_content and table_id:
                    # Reemplazar [tbl-0.md](tbl-0.md) por el contenido de la tabla
                    # Pero el markdown puede tener el enlace en diferentes formas
                    pattern = rf'\[{re.escape(table_id)}\]\([^)]+\)'
                    # Incrustar la tabla con formato Markdown
                    markdown = re.sub(pattern, f"\n\n{table_content}\n\n", markdown)
                    logger.debug(f"Tabla {table_id} incrustada en página {page_idx+1}")
            
            # ─────────────────────────────────────────────────────────────────
            # 3. Reemplazar referencias de imágenes por URLs locales
            # ─────────────────────────────────────────────────────────────────
            if image_url_map:
                markdown = _replace_image_refs(markdown, image_url_map)
            
            # ─────────────────────────────────────────────────────────────────
            # 4. Limpiar saltos de línea excesivos
            # ─────────────────────────────────────────────────────────────────
            markdown = re.sub(r'\n{3,}', '\n\n', markdown).strip()
            
            # ─────────────────────────────────────────────────────────────────
            # 5. Validar resultado
            # ─────────────────────────────────────────────────────────────────
            if not markdown or len(markdown) < 20:
                logger.warning(f"Página {page_idx+1}: markdown vacío o muy corto")
                results[page_idx] = MistralPageResult(page_index=page_idx, markdown="", accepted=False)
                pages_ko += 1
            else:
                results[page_idx] = MistralPageResult(
                    page_index=page_idx,
                    markdown=markdown,
                    image_urls=list(image_url_map.values()),
                    accepted=True,
                )
                pages_ok += 1
                logger.info(f"Página {page_idx+1}: {len(markdown):,} chars, {len(image_url_map)} imágenes, tabla incrustada")

        duration = time.monotonic() - start_time
        logger.info(f"Mistral OCR completado — enviadas={len(page_indices)}, OK={pages_ok}, fallidas={pages_ko}, duración={duration:.1f}s")

        return MistralBatchResult(
            pages=results,
            pages_sent=len(page_indices),
            pages_ok=pages_ok,
            pages_failed=pages_ko,
            duration_sec=duration,
            model=data.get("model", self.model),
        )