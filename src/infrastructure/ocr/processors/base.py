"""
Funciones auxiliares compartidas por todos los procesadores.

Incluye:
- Clasificación de páginas (la misma lógica que ya funciona en hybrid_router)
- Extracción local con PyMuPDF (gratuita)
- Detección de páginas vacías
"""

import fitz
import re
from typing import Tuple
from enum import Enum


class PageRoute(str, Enum):
    LOCAL = "local"
    OCR = "ocr"


class OCRMode(str, Enum):
    IMAGE = "image"
    TABLE = "table"
    IMAGE_TABLE = "image_table"


def is_page_meaningful(page: fitz.Page, text_content: str) -> bool:
    """Descarta páginas completamente vacías o irrelevantes."""
    alpha = len(re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ]', '', text_content))
    if alpha > 15:
        return True

    page_area = page.rect.width * page.rect.height
    for img in page.get_image_info():
        bbox = img.get("bbox", (0, 0, 0, 0))
        img_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        if page_area > 0 and (img_area / page_area) >= 0.05:
            return True

    return len(page.get_drawings()) > 5


def classify_page(page: fitz.Page) -> Tuple[PageRoute, OCRMode, str]:
    """
    Clasifica una página según su contenido (imagen, tabla, texto nativo).

    Reglas:
      - Vacía → LOCAL
      - Imagen grande + tabla → OCR (IMAGE_TABLE)
      - Imagen grande sola → OCR (IMAGE)
      - Tabla sola → OCR (TABLE)
      - Texto nativo suficiente → LOCAL
      - Resto → LOCAL

    Returns:
        route: PageRoute.LOCAL o PageRoute.OCR
        mode: OCRMode (solo relevante si route=OCR)
        reason: descripción legible para logs
    """
    text_raw = page.get_text("text").strip()
    alpha_chars = len(re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ]', '', text_raw))
    page_area = page.rect.width * page.rect.height

    # Vacía
    if alpha_chars < 10 and len(page.get_image_info()) == 0 and len(page.get_drawings()) < 3:
        return PageRoute.LOCAL, OCRMode.IMAGE, "vacía/irrelevante"

    # Detectar imagen grande (>=5% del área)
    has_big_image = False
    image_pct = 0.0
    for img in page.get_image_info():
        bbox = img.get("bbox", (0, 0, 0, 0))
        img_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        if page_area > 0 and (img_area / page_area) >= 0.05:
            has_big_image = True
            image_pct = img_area / page_area
            break

    # Detectar tabla (≥3 líneas horizontales y ≥2 verticales)
    drawings = page.get_drawings()
    h_lines = sum(
        1 for d in drawings
        for item in d.get("items", [])
        if item[0] == "l" and abs(item[2].y - item[1].y) < 2
    )
    v_lines = sum(
        1 for d in drawings
        for item in d.get("items", [])
        if item[0] == "l" and abs(item[2].x - item[1].x) < 2
    )
    has_table = h_lines >= 3 and v_lines >= 2

    # Reglas de clasificación
    if has_big_image and has_table:
        return (
            PageRoute.OCR,
            OCRMode.IMAGE_TABLE,
            f"imagen ({image_pct:.0%}) + tabla ({h_lines}h/{v_lines}v)",
        )
    if has_big_image:
        return PageRoute.OCR, OCRMode.IMAGE, f"imagen ({image_pct:.0%} del área)"
    if has_table:
        return PageRoute.OCR, OCRMode.TABLE, f"tabla ({h_lines}h/{v_lines}v líneas)"
    if alpha_chars >= 50:
        return PageRoute.LOCAL, OCRMode.IMAGE, f"texto nativo ({alpha_chars} chars)"

    return PageRoute.LOCAL, OCRMode.IMAGE, "sin contenido relevante para OCR"


def extract_local(page: fitz.Page) -> str:
    """
    Extrae texto de la página con PyMuPDF y lo convierte a Markdown básico.

    - Títulos detectados por tamaño de fuente relativo (>=1.4x mediana).
    - Párrafos agrupados sin prefijos.
    - Listas conservadas.
    """
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

    # Recopilar tamaños de fuente
    font_sizes = []
    for b in blocks:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                if span["text"].strip():
                    font_sizes.append(span["size"])

    if not font_sizes:
        return ""

    font_sizes.sort()
    median_size = font_sizes[len(font_sizes) // 2]
    title_threshold = median_size * 1.4

    paragraphs = []
    current_para = []
    current_level = None  # 1: '#', 2: '##', -1: lista, None: normal

    for b in blocks:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                if current_para:
                    paragraphs.append((" ".join(current_para), current_level))
                    current_para = []
                    current_level = None
                continue

            avg_size = sum(s["size"] for s in spans) / len(spans)
            text = " ".join(s["text"] for s in spans).strip()
            is_list = text.startswith(("- ", "• ", "* ", "● "))

            if avg_size >= title_threshold and not is_list:
                if current_para:
                    paragraphs.append((" ".join(current_para), current_level))
                    current_para = []
                level = 1 if avg_size >= median_size * 1.8 else 2
                paragraphs.append((text, level))
                current_level = None
            else:
                current_para.append(text)
                current_level = -1 if is_list else None

    if current_para:
        paragraphs.append((" ".join(current_para), current_level))

    md_lines = []
    for content, level in paragraphs:
        if level == 1:
            md_lines.append(f"# {content}")
        elif level == 2:
            md_lines.append(f"## {content}")
        elif level == -1:
            md_lines.append(content)
        else:
            md_lines.append(content)

    return "\n\n".join(md_lines)