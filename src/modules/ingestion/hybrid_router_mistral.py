"""
hybrid_router.py

Procesador híbrido de PDFs con soporte Mistral y DeepSeek.

Para Mistral:
  - Usa el campo 'tables' de la respuesta para incrustar tablas en Markdown.
  - Las imágenes ya vienen en base64 y se guardan localmente; se reemplazan las referencias.
  - No se añade sección extra de imágenes (ya están en el markdown).

Para DeepSeek:
  - Extrae coordenadas de imágenes desde el raw y recorta las imágenes del PDF.
  - Añade sección de imágenes al final del markdown.
"""

import fitz
import asyncio
import os
import re
import time
import json
import base64
from dataclasses import dataclass, field
from PIL import Image
import io
from src.shared.logging import get_logger
from src.shared.config import settings

logger = get_logger("hybrid_router")

DEBUG_DIR = os.path.join(os.getcwd(), "data", "debug")
IMAGES_DIR = os.path.join(os.getcwd(), "data", "extracted_images")
os.makedirs(DEBUG_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# SELECTOR DE PROVEEDOR OCR
# ──────────────────────────────────────────────────────────────────────────────
OCR_PROVIDER: str = getattr(settings, "OCR_PROVIDER", "mistral")

# ──────────────────────────────────────────────────────────────────────────────
# CLASIFICACIÓN DE PÁGINAS
# ──────────────────────────────────────────────────────────────────────────────

class PageRoute:
    LOCAL = "local"
    OCR = "ocr"

@dataclass
class PageClassification:
    page_num: int
    route: str
    reason: str
    has_image: bool = False
    has_table: bool = False
    alpha_chars: int = 0

def _classify_page(page: fitz.Page, page_num: int) -> PageClassification:
    """Clasifica la página según si necesita OCR (imagen grande o tabla)."""
    text_raw = page.get_text("text").strip()
    alpha_chars = len(re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ]', '', text_raw))
    page_area = page.rect.width * page.rect.height

    # Detectar imagen grande (>=5% del área)
    has_image = False
    image_pct = 0.0
    for img in page.get_image_info():
        bbox = img.get("bbox", (0,0,0,0))
        img_area = (bbox[2]-bbox[0]) * (bbox[3]-bbox[1])
        if page_area > 0 and (img_area / page_area) >= 0.05:
            has_image = True
            image_pct = img_area / page_area
            break

    # Detectar tabla por líneas de dibujo
    drawings = page.get_drawings()
    h_lines = sum(1 for d in drawings for item in d.get("items", []) if item[0]=="l" and abs(item[2].y-item[1].y)<2)
    v_lines = sum(1 for d in drawings for item in d.get("items", []) if item[0]=="l" and abs(item[2].x-item[1].x)<2)
    has_table = h_lines >= 3 and v_lines >= 2

    if has_image or has_table:
        reason = []
        if has_image: reason.append(f"imagen ({image_pct:.0%})")
        if has_table: reason.append(f"tabla ({h_lines}h/{v_lines}v)")
        return PageClassification(page_num, PageRoute.OCR, " + ".join(reason), has_image, has_table, alpha_chars)
    if alpha_chars >= 50:
        return PageClassification(page_num, PageRoute.LOCAL, f"texto nativo ({alpha_chars} chars)", alpha_chars=alpha_chars)
    return PageClassification(page_num, PageRoute.LOCAL, "sin contenido relevante", alpha_chars=alpha_chars)

def _is_page_meaningful(page: fitz.Page, text_content: str) -> bool:
    """Descarta páginas vacías o sin contenido relevante."""
    alpha = len(re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ]', '', text_content))
    if alpha > 15:
        return True
    page_area = page.rect.width * page.rect.height
    for img in page.get_image_info():
        bbox = img.get("bbox", (0,0,0,0))
        img_area = (bbox[2]-bbox[0])*(bbox[3]-bbox[1])
        if page_area > 0 and img_area/page_area > 0.05:
            return True
    return len(page.get_drawings()) > 5

def _extract_local(page: fitz.Page) -> str:
    """
    Extrae texto de la página con PyMuPDF y genera Markdown limpio.
    
    Reglas:
      - Los títulos se detectan por tamaño de fuente relativo (>= 1.4x mediana).
      - El texto normal se agrupa en párrafos (sin prefijos).
      - Las listas (líneas que empiezan con -, •, *) se conservan.
      - No se añaden ### ni otros prefijos innecesarios.
    """
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    
    # 1. Recopilar todos los tamaños de fuente de texto real (no vacío)
    font_sizes = []
    for b in blocks:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if text:
                    font_sizes.append(span["size"])
    
    if not font_sizes:
        return ""
    
    # Usar la mediana (menos sensible a outliers que el máximo)
    font_sizes.sort()
    median_size = font_sizes[len(font_sizes)//2]
    title_threshold = median_size * 1.4   # Un título debe ser al menos 1.4x más grande
    
    # 2. Procesar cada bloque/línea
    paragraphs = []
    current_para = []
    current_level = None  # 1: '#', 2: '##', None: normal
    
    for b in blocks:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                # Línea vacía -> cierra párrafo
                if current_para:
                    paragraphs.append((" ".join(current_para), current_level))
                    current_para = []
                    current_level = None
                continue
            
            # Calcular tamaño promedio de la línea
            avg_size = sum(s["size"] for s in spans) / len(spans)
            text = " ".join(s["text"] for s in spans).strip()
            
            # Detectar si es lista (empieza con -, •, *, etc.)
            is_list = text.startswith(("- ", "• ", "* ", "● "))
            
            # Si es un título por tamaño
            if avg_size >= title_threshold and not is_list:
                # Cerrar párrafo anterior
                if current_para:
                    paragraphs.append((" ".join(current_para), current_level))
                    current_para = []
                # Determinar nivel: # para muy grande, ## para mediano
                if avg_size >= median_size * 1.8:
                    level = 1
                else:
                    level = 2
                paragraphs.append((text, level))
                current_level = None
            else:
                # Texto normal o lista: acumular
                current_para.append(text)
                if is_list:
                    current_level = -1  # Marcador especial para listas
                else:
                    current_level = None
    
    # Cerrar último párrafo
    if current_para:
        paragraphs.append((" ".join(current_para), current_level))
    
    # 3. Convertir a Markdown
    md_lines = []
    for content, level in paragraphs:
        if level == 1:
            md_lines.append(f"# {content}")
        elif level == 2:
            md_lines.append(f"## {content}")
        elif level == -1:
            # Es una lista: ya tiene el prefijo, solo añadimos
            md_lines.append(content)
        else:
            # Párrafo normal
            md_lines.append(content)
    
    # Unir con doble salto de línea para separar párrafos/títulos
    return "\n\n".join(md_lines)

def _rasterize_page(page: fitz.Page, dpi: int = 150) -> bytes:
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return pix.tobytes("jpeg", jpg_quality=85)

# ──────────────────────────────────────────────────────────────────────────────
# PROCESADO OCR VÍA MISTRAL (con manejo de tablas)
# ──────────────────────────────────────────────────────────────────────────────

async def _process_pages_mistral(
    pdf_bytes: bytes,
    classifications: list[PageClassification],
    doc: fitz.Document,
    doc_id: str,
    ocr_adapter,
) -> dict[int, tuple[str, list[str]]]:
    """
    Procesa las páginas OCR usando Mistral.
    Utiliza el adaptador existente pero luego enriquece el markdown
    con las tablas extraídas del JSON crudo (guardado por el adaptador).
    """
    ocr_pages = [c for c in classifications if c.route == PageRoute.OCR]
    page_indices = [c.page_num for c in ocr_pages]

    logger.info(f"Mistral: enviando PDF con {len(page_indices)} páginas OCR: {[p+1 for p in page_indices]}")
    batch_result = await ocr_adapter.process_pdf_pages(
        pdf_bytes=pdf_bytes,
        page_indices=page_indices,
        doc_id=doc_id,
    )

    # Cargar el JSON crudo que el adaptador guardó en debug
    raw_json_path = os.path.join(DEBUG_DIR, f"{doc_id}_mistral_raw.json")
    try:
        with open(raw_json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        logger.warning(f"No se encontró JSON crudo de Mistral en {raw_json_path}. Las tablas no se podrán incrustar.")
        raw_data = {"pages": []}

    # Mapear índice de página -> datos completos (incluyendo tablas)
    page_data_map = {}
    for p in raw_data.get("pages", []):
        page_data_map[p["index"]] = p

    results: dict[int, tuple[str, list[str]]] = {}

    for page_idx, page_result in batch_result.pages.items():
        markdown = page_result.markdown
        image_urls = page_result.image_urls

        # ── Incrustar tablas si existen ───────────────────────────────────────
        page_data = page_data_map.get(page_idx)
        if page_data and "tables" in page_data:
            for table in page_data["tables"]:
                table_content = table.get("content", "")
                if table_content:
                    # Reemplazar el placeholder [tbl-*.md] por la tabla en Markdown
                    placeholder = f"[{table['id']}]({table['id']})"
                    markdown = markdown.replace(placeholder, f"\n\n{table_content}\n\n")
                    logger.debug(f"Tabla incrustada en página {page_idx+1}")

        # ── Asegurar que las imágenes se referencien con ruta local ───────────
        # El adaptador ya debería haber reemplazado las referencias en markdown.
        # Si no, lo hacemos aquí (pero el adaptador ya tiene _replace_image_refs)
        # No añadimos sección extra de imágenes.

        results[page_idx] = (markdown, image_urls)

    # Fallback para páginas no devueltas
    for cls in ocr_pages:
        if cls.page_num not in results:
            logger.warning(f"Mistral pág {cls.page_num+1}: no encontrada → fallback PyMuPDF")
            results[cls.page_num] = (_extract_local(doc[cls.page_num]), [])

    return results

# ──────────────────────────────────────────────────────────────────────────────
# PROCESADO OCR VÍA DEEPSEEK (página a página)
# ──────────────────────────────────────────────────────────────────────────────

async def _process_pages_deepseek(
    doc: fitz.Document,
    classifications: list[PageClassification],
    doc_id: str,
    ocr_adapter,
) -> dict[int, tuple[str, list[str]]]:
    """Envía cada página a DeepSeek y extrae coordenadas de imágenes."""
    results = {}
    ocr_pages = [c for c in classifications if c.route == PageRoute.OCR]
    total = len(ocr_pages)

    for i, cls in enumerate(ocr_pages, 1):
        page = doc[cls.page_num]
        img_bytes = await asyncio.to_thread(_rasterize_page, page, 150)

        # Modo según contenido
        mode = "image_table" if cls.has_image and cls.has_table else ("image" if cls.has_image else "table")
        logger.info(f"DeepSeek [{i}/{total}] pág {cls.page_num+1} modo={mode} — {cls.reason}")

        t0 = time.monotonic()
        ocr_result = await ocr_adapter.extract_once(img_bytes, mode=mode)
        elapsed = time.monotonic() - t0

        # Guardar raw para debug
        debug_path = os.path.join(DEBUG_DIR, f"{doc_id}_p{cls.page_num+1}_deepseek_raw.txt")
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(ocr_result.raw)

        if not ocr_result.accepted:
            logger.warning(f"DeepSeek pág {cls.page_num+1}: rechazado ({elapsed:.1f}s) → fallback PyMuPDF")
            results[cls.page_num] = (_extract_local(page), [])
        else:
            # Guardar imágenes recortadas
            image_urls = _save_deepseek_images(page, ocr_result.image_coords, doc_id, cls.page_num)
            logger.info(f"DeepSeek pág {cls.page_num+1}: OK — {len(ocr_result.clean):,} chars, {len(image_urls)} imágenes, {elapsed:.1f}s")
            results[cls.page_num] = (ocr_result.clean, image_urls)

    return results

def _save_deepseek_images(page: fitz.Page, bboxes: list, doc_id: str, page_num: int) -> list[str]:
    """Recorta imágenes del PDF a partir de coordenadas normalizadas (0-999)."""
    if not bboxes:
        return []
    pix = page.get_pixmap(dpi=150)
    full_img = Image.open(io.BytesIO(pix.tobytes("png")))
    w, h = full_img.size
    urls = []
    for idx, (x1,y1,x2,y2) in enumerate(bboxes):
        left = int(x1/999*w)
        top = int(y1/999*h)
        right = int(x2/999*w)
        bottom = int(y2/999*h)
        left, right = min(left,right), max(left,right)
        top, bottom = min(top,bottom), max(top,bottom)
        cropped = full_img.crop((left, top, right, bottom))
        fname = f"{doc_id}_p{page_num+1}_img{idx}.png"
        cropped.save(os.path.join(IMAGES_DIR, fname))
        urls.append(f"/data/extracted_images/{fname}")
    return urls

# ──────────────────────────────────────────────────────────────────────────────
# PROCESADOR PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────

class HybridDocumentProcessor:
    """
    Procesador híbrido de PDFs.

    Fase 1: Clasifica páginas localmente (PyMuPDF) para decidir si necesitan OCR.
    Fase 2: Procesa páginas LOCAL con PyMuPDF y páginas OCR con el proveedor elegido.
    Para Mistral: incrusta tablas automáticamente desde el JSON de respuesta.
    Para DeepSeek: extrae imágenes y las guarda localmente.
    """

    def __init__(self, ocr_adapter=None):
        self.provider = OCR_PROVIDER
        self.ocr = ocr_adapter or self._build_adapter()
        logger.info(f"HybridDocumentProcessor iniciado — OCR provider: {self.provider.upper()}")

    def _build_adapter(self):
        if self.provider == "mistral":
            from src.infrastructure.ocr.mistral_adapter import MistralOCRAdapter
            return MistralOCRAdapter()
        elif self.provider == "deepseek":
            from src.infrastructure.ocr.deepseek_adapter import DeepSeekOCRAdapter
            return DeepSeekOCRAdapter()
        else:
            raise ValueError(f"OCR_PROVIDER desconocido: '{self.provider}'")

    async def process_pdf(self, pdf_bytes: bytes, doc_id: str) -> str:
        t_start = time.monotonic()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)

        logger.info(f"═══════════════════════════════════════════════════════════════")
        logger.info(f"INICIO procesamiento PDF — doc_id={doc_id}, páginas={total_pages}, provider={self.provider.upper()}")
        logger.info(f"═══════════════════════════════════════════════════════════════")

        # ── FASE 1: Clasificación local ─────────────────────────────────────────
        t1 = time.monotonic()
        logger.info("FASE 1 — Análisis local (PyMuPDF, sin API)")
        classifications = []
        skipped = []
        for pnum in range(total_pages):
            page = doc[pnum]
            text = page.get_text("text").strip()
            if not _is_page_meaningful(page, text):
                logger.info(f"  Pág {pnum+1}/{total_pages}: OMITIDA (vacía)")
                skipped.append(pnum)
                continue
            cls = _classify_page(page, pnum)
            classifications.append(cls)
            logger.info(f"  Pág {pnum+1}/{total_pages}: {cls.route.upper():5s} ← {cls.reason}")
        local_pages = [c for c in classifications if c.route == PageRoute.LOCAL]
        ocr_pages = [c for c in classifications if c.route == PageRoute.OCR]
        logger.info(f"FASE 1 completada en {time.monotonic()-t1:.2f}s — LOCAL={len(local_pages)}, OCR={len(ocr_pages)}, OMITIDAS={len(skipped)}")

        # ── FASE 2: Procesamiento ───────────────────────────────────────────────
        t2 = time.monotonic()
        logger.info(f"FASE 2 — Construcción ({self.provider.upper()})")
        page_results: dict[int, tuple[str, list[str]]] = {}

        # 2a. Páginas LOCAL
        logger.info(f"  Procesando {len(local_pages)} páginas LOCAL con PyMuPDF...")
        for cls in local_pages:
            page = doc[cls.page_num]
            page_results[cls.page_num] = (_extract_local(page), [])

        # 2b. Páginas OCR
        if ocr_pages:
            logger.info(f"  Procesando {len(ocr_pages)} páginas OCR con {self.provider.upper()}...")
            if self.provider == "mistral":
                ocr_results = await _process_pages_mistral(pdf_bytes, classifications, doc, doc_id, self.ocr)
            else:
                ocr_results = await _process_pages_deepseek(doc, classifications, doc_id, self.ocr)
            page_results.update(ocr_results)
        else:
            logger.info("  Sin páginas OCR — no se llama a ninguna API")

        # ── ENSAMBLADO FINAL ────────────────────────────────────────────────────
        parts = []
        for cls in classifications:  # orden original
            pn = cls.page_num
            md, urls = page_results.get(pn, ("", []))
            header = f"\n\n{'='*40}\n📄 PÁGINA {pn+1}  [{cls.route.upper()}]\n{'='*40}\n\n"
            # Para Mistral, las imágenes ya están incrustadas en 'md' (por el adaptador)
            # No añadimos sección extra. Para DeepSeek sí.
            if self.provider == "deepseek" and urls:
                img_section = "\n\n**Imágenes extraídas:**\n" + "\n".join(f"![Imagen]({url})" for url in urls)
            else:
                img_section = ""
            parts.append(header + md + img_section)

        doc.close()
        final_md = "".join(parts)

        debug_path = os.path.join(DEBUG_DIR, f"{doc_id}_final.md")
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(final_md)

        t_total = time.monotonic() - t_start
        logger.info(f"═══════════════════════════════════════════════════════════════")
        logger.info(f"FIN procesamiento — doc_id={doc_id}, páginas_procesadas={len(classifications)}, local={len(local_pages)}, ocr={len(ocr_pages)}, omitidas={len(skipped)}, chars_md={len(final_md):,}, tiempo_total={t_total:.1f}s")
        logger.info(f"═══════════════════════════════════════════════════════════════")
        return final_md