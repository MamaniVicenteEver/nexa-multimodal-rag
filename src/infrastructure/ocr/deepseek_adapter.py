"""
DeepSeekOCRAdapter — Usa los tokens especiales de deepseek-ocr-2 correctamente.

El modelo tiene 3 modos según lo que se ponga en system:

  MODO A — "<image>"        → Markdown completo + detección de layout
                               Devuelve coords de imágenes: image[[x1,y1,x2,y2]]
                               Ideal para: páginas con imagen sola, o imagen + texto

  MODO B — "<|grounding|>"  → Extracción estructurada con bounding-boxes de texto
                               Ideal para: páginas con tablas, o tablas + texto

  MODO C — "<image>" +      → Combinado: detecta layout Y estructura de tabla
           "<|grounding|>"   Ideal para: páginas con imagen + tabla juntas

El router clasifica la página ANTES de llamar y elige el modo correcto.
temperature=1.0 es el punto óptimo encontrado experimentalmente.
"""

from openai import AsyncOpenAI
import base64
import re
from dataclasses import dataclass, field
from src.core.ports.ocr_provider import IOCRProvider
from src.shared.config import settings
from src.shared.logging import get_logger

logger = get_logger("deepseek_ocr")


# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DEL MODELO (valores óptimos encontrados experimentalmente)
# ──────────────────────────────────────────────────────────────────────────────

MODEL_PARAMS = dict(
    max_tokens        = 4096,
    temperature       = 0,   # <1 pierde info, >1 inventa — 1.0 es el punto justo
    top_p             = 1,
    presence_penalty  = 0.,
    frequency_penalty = 0,
    extra_body        = {
        "top_k":              50,
        "repetition_penalty": 1,
        "min_p":              0,
    },
)
# Tokens especiales del modelo
_TOKEN_IMAGE     = "<image> Extract image elements only."        # activa detección de layout + coords de imagen
_TOKEN_GROUNDING = "|grounding|>Convert this document to Markdown and extract all tables."  # activa extracción estructurada con bounding-boxes


# ──────────────────────────────────────────────────────────────────────────────
# TIPOS DE LLAMADA
# ──────────────────────────────────────────────────────────────────────────────

class OCRMode:
    IMAGE         = "image"          # página con imagen (± texto)
    TABLE         = "table"          # página con tabla (± texto)
    IMAGE_TABLE   = "image_table"    # página con imagen + tabla


# ──────────────────────────────────────────────────────────────────────────────
# PROMPTS POR MODO
# ──────────────────────────────────────────────────────────────────────────────

# Las instrucciones son cortas y directas — el modelo se desorienta con prompts largos.

_SYSTEM = {
    OCRMode.IMAGE: _TOKEN_IMAGE,
    OCRMode.TABLE: _TOKEN_GROUNDING,
    OCRMode.IMAGE_TABLE: f"{_TOKEN_IMAGE}\n{_TOKEN_GROUNDING}",
}

_USER_PROMPT = {
    OCRMode.IMAGE: (
        "Convert this document page to structured Markdown.\n"
        "- Detect all images and return their bounding box coordinates.\n"
        "- Preserve headings, paragraphs, and lists.\n"
        "- Output only the Markdown content."
    ),
    OCRMode.TABLE: (
        "Convert this document page to structured Markdown.\n"
        "- Format all tables using Markdown pipe syntax (| col | col |).\n"
        "- Preserve all text outside the tables as-is.\n"
        "- Output only the Markdown content."
    ),
    OCRMode.IMAGE_TABLE: (
        "Convert this document page to structured Markdown.\n"
        "- Detect all images and return their bounding box coordinates.\n"
        "- Format all tables using Markdown pipe syntax (| col | col |).\n"
        "- Preserve headings, paragraphs, and lists.\n"
        "- Output only the Markdown content."
    ),
}


# ──────────────────────────────────────────────────────────────────────────────
# RESULTADO
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class OCRResult:
    raw:   str                    # output exacto del modelo (para debug + coords)
    clean: str                    # texto limpio listo para el .md final
    mode:  str                    # qué modo se usó
    image_coords: list = field(default_factory=list)  # [(x1,y1,x2,y2), ...]
    accepted: bool = True         # False → el router debe usar PyMuPDF


# ──────────────────────────────────────────────────────────────────────────────
# EXTRACCIÓN DE COORDENADAS DE IMAGEN
# ──────────────────────────────────────────────────────────────────────────────

def _extract_image_coords(raw: str) -> list[tuple]:
    """
    Extrae bounding boxes del formato image[[x1,y1,x2,y2]] que devuelve el modelo.
    Coordenadas normalizadas 0-999. Filtra áreas menores a 800 (ruido).
    """
    coords = []
    for x1, y1, x2, y2 in re.findall(
        r'image\[\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]\]', raw
    ):
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        if 0 <= x1 < x2 <= 999 and 0 <= y1 < y2 <= 999:
            if (x2 - x1) * (y2 - y1) >= 800:
                coords.append((x1, y1, x2, y2))
            else:
                logger.debug(f"Coord ignorada (área pequeña): {x1},{y1},{x2},{y2}")
        else:
            logger.debug(f"Coord inválida ignorada: {x1},{y1},{x2},{y2}")
    return coords


# ──────────────────────────────────────────────────────────────────────────────
# LIMPIEZA DEL OUTPUT
# ──────────────────────────────────────────────────────────────────────────────

# Frases conversacionales que el modelo a veces genera (no son OCR)
_CONVERSATIONAL = re.compile(
    r"^(if there'?s?\s+an? error"
    r"|please\s+(provide|give|note|see)"
    r"|i\s+(can'?t|cannot)\s+"
    r"|i'?m\s+(sorry|unable)"
    r"|as an ai\b"
    r"|use plaintext for"
    r"|no images.*allowed"
    r"|only textual data"
    r"|feedback so i know"
    r"|things went wrong)",
    re.IGNORECASE,
)

_HALLUCINATION = re.compile(
    r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af'   # CJK
    r'\u0600-\u06ff\u0590-\u05ff]',                # árabe/hebreo
)


def _clean(raw: str) -> str:
    """
    Limpieza mínima y quirúrgica del output del modelo:
    1. Elimina etiquetas de grounding <|...|>
    2. Elimina coordenadas de bounding-box del texto (quedan en image_coords)
    3. Elimina líneas con CJK/árabe o frases conversacionales inventadas
    4. Normaliza saltos de línea
    No elimina líneas de tabla ni números válidos.
    """
    # 1. Etiquetas de grounding
    text = re.sub(r'<\|[^|]*\|>', '', raw)

    # 2. Coordenadas de imagen del texto (ya fueron extraídas en image_coords)
    text = re.sub(r'image\[\[\d+[,\s\d]*\]\]', '', text)
    # Otros tipos de coordenadas sueltas (title[[...]], text[[...]], etc.)
    text = re.sub(r'\w+\[\[\d+[,\s\d]*\]\]', '', text)

    # 3. Filtrar línea a línea
    clean_lines = []
    for line in text.split('\n'):
        stripped = line.strip()

        # Vacía → conservar (estructura del documento)
        if not stripped:
            clean_lines.append('')
            continue

        # CJK o árabe → eliminar
        if _HALLUCINATION.search(stripped):
            logger.debug(f"Línea CJK/árabe eliminada: {stripped[:60]!r}")
            continue

        # Frases conversacionales → eliminar
        if _CONVERSATIONAL.match(stripped):
            logger.debug(f"Línea conversacional eliminada: {stripped[:60]!r}")
            continue

        # Línea larguísima sin espacios (basura concatenada) → eliminar
        if len(stripped) > 300 and stripped.count(' ') < 5:
            logger.debug(f"Línea basura larga eliminada ({len(stripped)} chars)")
            continue

        clean_lines.append(line)

    # 4. Normalizar saltos de línea múltiples
    result = '\n'.join(clean_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


def _is_useful(text: str) -> bool:
    """True si el texto tiene al menos algún contenido real."""
    return bool(re.search(r'[a-zA-ZáéíóúÁÉÍÓÚñÑ]{3,}', text))


# ──────────────────────────────────────────────────────────────────────────────
# ADAPTADOR
# ──────────────────────────────────────────────────────────────────────────────

class DeepSeekOCRAdapter(IOCRProvider):
    """
    Adaptador OCR para deepseek/deepseek-ocr-2 via Novita.

    Método principal: extract_once(file_bytes, mode) → OCRResult
      - UNA sola llamada a la API por página
      - El modo determina qué tokens especiales se usan en system
      - Devuelve raw (para debug), clean (para el .md), image_coords (para recortar)

    El router elige el modo según la clasificación de la página:
      - OCRMode.IMAGE       → imagen sola o imagen + texto
      - OCRMode.TABLE       → tabla sola o tabla + texto
      - OCRMode.IMAGE_TABLE → imagen + tabla (juntas en la misma página)
    """

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.NOVITA_API_KEY,
            base_url=settings.NOVITA_BASE_URL,
            timeout=120.0,
        )
        self.model = settings.NOVITA_OCR_MODEL   # "deepseek/deepseek-ocr-2"

    async def extract_once(
        self,
        file_bytes: bytes,
        mode: str = OCRMode.IMAGE,
    ) -> OCRResult:
        """
        Llama a la API UNA sola vez con el modo correcto.

        Args:
            file_bytes: imagen JPEG de la página (ya rasterizada)
            mode:       OCRMode.IMAGE | OCRMode.TABLE | OCRMode.IMAGE_TABLE

        Returns:
            OCRResult con raw, clean, image_coords y accepted.
            Si accepted=False → el router debe usar PyMuPDF como fallback.
        """
        img_b64 = base64.b64encode(file_bytes).decode('utf-8')
        system  = _SYSTEM[mode]
        user    = _USER_PROMPT[mode]

        logger.info(f"OCR llamada: modo={mode}, system_token={system!r}")

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ""},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_b64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            **MODEL_PARAMS,
        )

        raw = response.choices[0].message.content or ""
        logger.debug(f"OCR raw ({len(raw):,} chars):\n{raw[:300]}")

        # Extraer coordenadas de imagen ANTES de limpiar
        image_coords = _extract_image_coords(raw)
        if image_coords:
            logger.info(f"OCR: {len(image_coords)} coordenadas de imagen detectadas")

        # Limpiar el texto
        clean = _clean(raw)

        # ¿El output es útil?
        if not _is_useful(clean):
            logger.warning(
                f"OCR: output sin contenido útil tras limpieza "
                f"(modo={mode}). Fallback a PyMuPDF."
            )
            return OCRResult(
                raw=raw, clean="", mode=mode,
                image_coords=image_coords, accepted=False,
            )

        logger.info(f"OCR: aceptado — {len(clean):,} chars, {len(image_coords)} imágenes")
        return OCRResult(
            raw=raw, clean=clean, mode=mode,
            image_coords=image_coords, accepted=True,
        )

    # ── Compatibilidad con IOCRProvider ───────────────────────────────────────

    async def extract_raw(self, file_bytes: bytes) -> str:
        result = await self.extract_once(file_bytes, mode=OCRMode.IMAGE)
        return result.raw

    async def extract(self, file_bytes: bytes) -> str:
        result = await self.extract_once(file_bytes, mode=OCRMode.IMAGE)
        return result.clean if result.accepted else ""