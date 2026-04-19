import fitz  # PyMuPDF
import asyncio
import os
import re
from PIL import Image
import io
from src.core.ports.ocr_provider import IOCRProvider
from src.shared.logging import get_logger

# OCRResult se importa en tiempo de ejecución para evitar importación circular.
# El router llama a visual_ocr.extract_once() que devuelve un OCRResult,
# pero no necesita la clase directamente — solo accede a sus atributos.

logger = get_logger("hybrid_router")

DEBUG_DIR = os.path.join(os.getcwd(), "data", "debug")
IMAGES_DIR = os.path.join(os.getcwd(), "data", "extracted_images")
os.makedirs(DEBUG_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

def _rasterize_page_cpu_bound(page: fitz.Page, dpi: int = 150) -> bytes:
    """Convierte una página de PDF a bytes de imagen JPEG para enviar a OCR."""
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return pix.tobytes("jpeg", jpg_quality=85)


# ──────────────────────────────────────────────────────────────────────────────
# CLASIFICADOR DE RUTA POR PÁGINA
# ──────────────────────────────────────────────────────────────────────────────

class PageRoute:
    LOCAL = "local"   # PyMuPDF extrae texto directamente (gratis, sin API)
    OCR   = "ocr"     # Enviar al OCR visual con el modo correcto


# Modos OCR — deben coincidir con OCRMode en deepseek_ocr.py
class OCRMode:
    IMAGE       = "image"        # <image>             → layout + coords de imagen
    TABLE       = "table"        # <|grounding|>       → tabla con pipes
    IMAGE_TABLE = "image_table"  # <image>+<|grounding|> → imagen + tabla


def _classify_page(page: fitz.Page) -> tuple[str, str, str]:
    """
    Clasifica la página y decide:
      - route:    PageRoute.LOCAL o PageRoute.OCR
      - ocr_mode: OCRMode.IMAGE | TABLE | IMAGE_TABLE (solo relevante si route=OCR)
      - reason:   descripción para el log

    Reglas (en orden de prioridad):

    1. VACÍA → LOCAL
    2. IMAGEN GRANDE + TABLA → OCR modo IMAGE_TABLE
       (la página más compleja: imagen + tabla juntas)
    3. IMAGEN GRANDE sola → OCR modo IMAGE
    4. TABLA sola → OCR modo TABLE
    5. TEXTO NATIVO suficiente → LOCAL (PyMuPDF lo maneja perfecto)
    6. RESTO → LOCAL (sin contenido relevante para el OCR)
    """
    text_raw    = page.get_text("text").strip()
    alpha_chars = len(re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ]', '', text_raw))
    page_area   = page.rect.width * page.rect.height

    # ── Regla 1: página vacía ─────────────────────────────────────────────────
    if alpha_chars < 10 and len(page.get_image_info()) == 0 and len(page.get_drawings()) < 3:
        return PageRoute.LOCAL, OCRMode.IMAGE, "vacía/irrelevante"

    # ── Detectar imagen grande (≥ 5% del área) ────────────────────────────────
    has_big_image = False
    image_pct     = 0.0
    for img in page.get_image_info():
        bbox     = img.get("bbox", (0, 0, 0, 0))
        img_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        if page_area > 0 and (img_area / page_area) >= 0.05:
            has_big_image = True
            image_pct     = img_area / page_area
            break

    # ── Detectar tabla (≥ 3 líneas h + ≥ 2 líneas v en drawings) ─────────────
    drawings = page.get_drawings()
    h_lines  = sum(
        1 for d in drawings
        for item in d.get("items", [])
        if item[0] == "l" and abs(item[2].y - item[1].y) < 2
    )
    v_lines  = sum(
        1 for d in drawings
        for item in d.get("items", [])
        if item[0] == "l" and abs(item[2].x - item[1].x) < 2
    )
    has_table = h_lines >= 3 and v_lines >= 2

    # ── Regla 2: imagen + tabla → modo IMAGE_TABLE ────────────────────────────
    if has_big_image and has_table:
        return (
            PageRoute.OCR,
            OCRMode.IMAGE_TABLE,
            f"imagen ({image_pct:.0%}) + tabla ({h_lines}h/{v_lines}v)",
        )

    # ── Regla 3: imagen sola → modo IMAGE ────────────────────────────────────
    if has_big_image:
        return PageRoute.OCR, OCRMode.IMAGE, f"imagen ({image_pct:.0%} del área)"

    # ── Regla 4: tabla sola → modo TABLE ─────────────────────────────────────
    if has_table:
        return PageRoute.OCR, OCRMode.TABLE, f"tabla ({h_lines}h/{v_lines}v líneas)"

    # ── Regla 5: texto nativo suficiente → LOCAL ──────────────────────────────
    if alpha_chars >= 50:
        return PageRoute.LOCAL, OCRMode.IMAGE, f"texto nativo ({alpha_chars} chars)"

    # ── Regla 6: nada relevante → LOCAL ──────────────────────────────────────
    return PageRoute.LOCAL, OCRMode.IMAGE, "sin contenido relevante para OCR"


# ──────────────────────────────────────────────────────────────────────────────
# EXTRACCIÓN LOCAL CON PyMuPDF  (sin llamada a API)
# ──────────────────────────────────────────────────────────────────────────────

def _extract_local(page: fitz.Page) -> str:
    """
    Extrae texto de la página con PyMuPDF y lo convierte a Markdown básico.
    Detecta bloques de texto, encabezados (por tamaño de fuente) y listas.
    """
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    lines_out = []

    # Recopilar todos los tamaños de fuente para normalizar encabezados
    all_sizes = [
        span["size"]
        for b in blocks if b["type"] == 0
        for line in b["lines"]
        for span in line["spans"]
        if span["text"].strip()
    ]
    max_size = max(all_sizes, default=12)

    for b in blocks:
        if b["type"] != 0:          # 0 = texto, 1 = imagen (ignoramos aquí)
            continue
        for line in b["lines"]:
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue

            text     = " ".join(s["text"] for s in spans).strip()
            avg_size = sum(s["size"] for s in spans) / len(spans)
            is_bold  = any(s["flags"] & 16 for s in spans)  # flag bold

            # Elegir prefijo Markdown según tamaño relativo
            ratio = avg_size / max_size if max_size else 1
            if ratio >= 0.90 or (is_bold and ratio >= 0.80):
                prefix = "## "
            elif ratio >= 0.75:
                prefix = "### "
            else:
                # Detectar listas simples
                stripped = text.lstrip()
                if stripped.startswith(("•", "-", "●", "○", "*")):
                    prefix = ""   # ya tiene su marcador
                else:
                    prefix = ""

            lines_out.append(f"{prefix}{text}")

    return "\n".join(lines_out)


# ──────────────────────────────────────────────────────────────────────────────
# LIMPIEZA DEL OUTPUT OCR
# ──────────────────────────────────────────────────────────────────────────────

def _clean_ocr_markdown(raw_markdown: str) -> str:
    """
    Limpia el output crudo del OCR:
    - Elimina coordenadas image[[...]], title[[...]], etc.
    - Elimina etiquetas <|...|>
    - Elimina líneas con caracteres chinos o CJK
    - Elimina líneas con HTML o URLs inventadas
    - Normaliza saltos de línea
    """
    # Eliminar etiquetas de grounding
    clean = re.sub(r'<\|.*?\|>', '', raw_markdown)
    # Eliminar coordenadas de bounding-box
    clean = re.sub(r'\w+\[\[\d+[^\]]*\]\]', '', clean)
    # Líneas a filtrar
    lines = clean.split('\n')
    filtered = []
    garbage_keywords = [
        'DOCTYPE', '<html', '<body', '<div', '<span', '<table', '<tr', '<td',
        'https://', 'http://', 'www.', '.com', '.org', '.es', 'mailto:',
        '```html', '```python', 'Lorem ipsum', 'placeholder',
    ]
    for line in lines:
        stripped = line.strip()
        # Saltar líneas vacías (se normalizarán después)
        if not stripped:
            filtered.append('')
            continue
        # Saltar si contiene CJK (chino/japonés/coreano)
        if re.search(r'[\u4e00-\u9fff\u3040-\u30ff]', stripped):
            continue
        # Saltar si contiene etiquetas HTML
        if re.search(r'<[a-zA-Z/][^>]*>', stripped):
            continue
        # Saltar si contiene basura conocida
        if any(kw.lower() in stripped.lower() for kw in garbage_keywords):
            continue
        # Saltar tokens de markdown inútiles solos
        if stripped in ('title', 'sub_title', 'text', 'image', 'table', 'image[[', '```'):
            continue
        # Saltar líneas extremadamente largas sin espacios (basura OCR)
        if len(stripped) > 300 and stripped.count(' ') < 5:
            continue
        filtered.append(line)

    clean = '\n'.join(filtered)
    # Normalizar múltiples saltos de línea
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    return clean.strip()


# ──────────────────────────────────────────────────────────────────────────────
# EXTRACCIÓN DE COORDENADAS DE IMÁGENES (para recortar del PDF)
# ──────────────────────────────────────────────────────────────────────────────

def _extract_image_coordinates(raw_markdown: str) -> list:
    """
    Extrae coordenadas normalizadas (0-999) del formato image[[x1,y1,x2,y2]].
    Filtra coordenadas inválidas o áreas menores a 800.
    """
    pattern = r'image\[\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]\]'
    matches = re.findall(pattern, raw_markdown)
    valid = []
    for x1, y1, x2, y2 in matches:
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        if (0 <= x1 < x2 <= 999 and 0 <= y1 < y2 <= 999):
            if (x2 - x1) * (y2 - y1) >= 800:
                valid.append((x1, y1, x2, y2))
            else:
                logger.debug(f"Imagen pequeña ignorada: {x1},{y1},{x2},{y2}")
        else:
            logger.warning(f"Coordenada inválida ignorada: {x1},{y1},{x2},{y2}")
    return valid


# ──────────────────────────────────────────────────────────────────────────────
# RECORTE Y GUARDADO DE IMÁGENES
# ──────────────────────────────────────────────────────────────────────────────

def _save_cropped_images(
    page: fitz.Page,
    bboxes: list,
    doc_id: str,
    page_num: int,
) -> list[str]:
    """
    Dado un listado de bboxes normalizados (0-999), recorta las imágenes
    de la página y las guarda en IMAGES_DIR. Devuelve las URLs relativas.
    """
    if not bboxes:
        return []

    pix            = page.get_pixmap(dpi=150)
    img_data       = pix.tobytes("png")
    full_page_img  = Image.open(io.BytesIO(img_data))
    pw, ph         = full_page_img.size
    urls           = []

    for idx, (x1, y1, x2, y2) in enumerate(bboxes):
        left   = int(x1 / 999 * pw)
        top    = int(y1 / 999 * ph)
        right  = int(x2 / 999 * pw)
        bottom = int(y2 / 999 * ph)
        left, right = min(left, right), max(left, right)
        top, bottom = min(top, bottom), max(top, bottom)

        cropped      = full_page_img.crop((left, top, right, bottom))
        img_filename = f"{doc_id}_p{page_num+1}_img{idx}.png"
        img_path     = os.path.join(IMAGES_DIR, img_filename)
        cropped.save(img_path)
        urls.append(f"/data/extracted_images/{img_filename}")
        logger.debug(f"Imagen guardada: {img_path}")

    return urls


# ──────────────────────────────────────────────────────────────────────────────
# PROCESADOR PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────

class HybridDocumentProcessor:
    def __init__(self, visual_ocr_adapter: IOCRProvider):
        self.visual_ocr = visual_ocr_adapter

    def _is_page_meaningful(self, page: fitz.Page, text_content: str) -> bool:
        """Descarta páginas completamente vacías (sin texto, sin imágenes, sin dibujos)."""
        alpha_chars = len(re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ]', '', text_content))
        if alpha_chars > 15:
            return True
        page_area = page.rect.width * page.rect.height
        for img in page.get_image_info():
            bbox     = img.get("bbox", (0, 0, 0, 0))
            img_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            if page_area > 0 and (img_area / page_area) > 0.05:
                return True
        if len(page.get_drawings()) > 5:
            return True
        return False

    async def process_pdf(self, pdf_bytes: bytes, doc_id: str) -> str:
        doc         = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        parts       = []

        logger.info("Iniciando procesamiento de PDF", extra={"doc_id": doc_id})

        stats = {"local": 0, "ocr": 0, "skipped": 0}

        for page_num in range(total_pages):
            page         = doc[page_num]
            text_content = page.get_text("text").strip()
            logger.info(f"Procesando página {page_num + 1}/{total_pages}")

            # ── Filtro de página vacía ────────────────────────────────────────
            if not self._is_page_meaningful(page, text_content):
                logger.info(f"Página {page_num+1} descartada (vacía/irrelevante)")
                stats["skipped"] += 1
                continue

            # ── Clasificar ruta y modo OCR ────────────────────────────────────
            route, ocr_mode, reason = _classify_page(page)
            logger.info(
                f"Página {page_num+1} → {route.upper()} "
                f"{'[' + ocr_mode + ']' if route == PageRoute.OCR else ''} "
                f"({reason})"
            )

            image_urls = []

            if route == PageRoute.LOCAL:
                # ── RUTA LOCAL: PyMuPDF extrae el texto directamente ──────────
                page_text = _extract_local(page)
                stats["local"] += 1

            else:
                # ── RUTA OCR: UNA sola llamada con el modo correcto ───────────
                image_bytes = await asyncio.to_thread(
                    _rasterize_page_cpu_bound, page, 150
                )

                # extract_once → una llamada, devuelve raw + clean + image_coords
                ocr_result = await self.visual_ocr.extract_once(image_bytes, mode=ocr_mode)

                # Guardar raw en disco SIEMPRE (para auditoría)
                debug_path = os.path.join(
                    DEBUG_DIR, f"{doc_id}_page{page_num+1}_raw.txt"
                )
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(ocr_result.raw)

                if not ocr_result.accepted:
                    # ── FALLBACK: OCR no produjo nada útil → PyMuPDF ──────────
                    logger.warning(
                        f"Página {page_num+1}: OCR rechazado (modo={ocr_mode}). "
                        f"Usando PyMuPDF como fallback."
                    )
                    page_text  = _extract_local(page)
                    image_urls = []
                    stats["ocr_fallback"] = stats.get("ocr_fallback", 0) + 1
                else:
                    # ── OCR aceptado ──────────────────────────────────────────
                    # Las coords vienen del OCRResult directamente (ya extraídas)
                    image_urls = _save_cropped_images(
                        page, ocr_result.image_coords, doc_id, page_num
                    )
                    logger.info(
                        f"Página {page_num+1}: {len(ocr_result.image_coords)} "
                        f"imágenes detectadas, modo={ocr_mode}"
                    )
                    page_text = ocr_result.clean

                stats["ocr"] += 1

            # ── Ensamblar contenido de la página ─────────────────────────────
            header = (
                f"\n\n{'='*40}\n"
                f"📄 PÁGINA {page_num + 1}\n"
                f"{'='*40}\n\n"
            )
            images_md = ""
            if image_urls:
                images_md = "\n\n**Imágenes extraídas:**\n" + "\n".join(
                    f"![Imagen]({url})" for url in image_urls
                )

            parts.append(header + page_text + images_md)

        doc.close()

        ocr_fallback = stats.get("ocr_fallback", 0)
        logger.info(
            f"Procesamiento completado. "
            f"Local: {stats['local']} | OCR OK: {stats['ocr'] - ocr_fallback} | "
            f"OCR→fallback PyMuPDF: {ocr_fallback} | "
            f"Omitidas: {stats['skipped']} | "
            f"Total procesadas: {stats['local'] + stats['ocr']}"
        )

        final_markdown = "".join(parts)

        # Guardar debug final
        debug_filepath = os.path.join(DEBUG_DIR, f"{doc_id}_final.md")
        with open(debug_filepath, "w", encoding="utf-8") as f:
            f.write(final_markdown)

        return final_markdown