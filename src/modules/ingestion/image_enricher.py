import re
import asyncio
from typing import Optional
from src.core.domain.chunk import Chunk
from src.core.ports.vision_provider import IVisionProvider
from src.shared.logging import get_logger

logger = get_logger("image_enricher")

class ImageEnricher:
    def __init__(self, vision_provider: IVisionProvider):
        self.vision = vision_provider

    async def extract_and_process(
        self,
        markdown_text: str,
        doc_id: str,
        page_number: Optional[int] = None   # <-- NUEVO parámetro opcional
    ) -> tuple[str, list[Chunk]]:
        """
        Extrae las imágenes, lanza peticiones a Gemini en paralelo, y devuelve:
        1. El Markdown limpio (sin etiquetas de imagen ruidosas) para el Chunker.
        2. La lista de Chunks de tipo "imagen" ya instanciados.
        """
        # Busca etiquetas: ![alt](url)
        pattern = re.compile(r'!\[.*?\]\((.*?)\)')
        matches = list(pattern.finditer(markdown_text))

        if not matches:
            return markdown_text, []

        logger.info(f"Se detectaron {len(matches)} imágenes. Lanzando Gemini en paralelo...")
        
        image_tasks = []
        clean_markdown = markdown_text

        for match in matches:
            full_tag = match.group(0)
            image_url = match.group(1)

            start, end = match.span()
            # Contexto: 500 caracteres antes y después
            ctx_before = markdown_text[max(0, start-500):start]
            ctx_after = markdown_text[end:min(len(markdown_text), end+500)]
            context = f"...{ctx_before}\n[IMAGEN]\n{ctx_after}..."

            # 1. Crear la tarea asíncrona (pasamos también page_number)
            image_tasks.append(self._process_single_image(image_url, context, doc_id, page_number))
            
            # 2. Limpiar el Markdown reemplazando la imagen por un marcador sutil
            clean_markdown = clean_markdown.replace(full_tag, f"\n> *[Ref visual: {image_url}]*\n")

        # Ejecutamos TODAS las llamadas a Gemini al mismo tiempo
        results = await asyncio.gather(*image_tasks, return_exceptions=True)

        image_chunks = []
        for idx, res in enumerate(results):
            if isinstance(res, Chunk):
                image_chunks.append(res)
                logger.debug(f"Imagen {idx+1}/{len(results)} procesada correctamente")
            else:
                logger.error(
                    f"Fallo al procesar imagen {idx+1}/{len(results)}: {type(res).__name__} - {str(res)}",
                    exc_info=res if isinstance(res, Exception) else None
                )

        return clean_markdown, image_chunks

    async def _process_single_image(
        self,
        image_url: str,
        context: str,
        doc_id: str,
        page_number: Optional[int] = None
    ) -> Chunk:
        description = await self.vision.describe_image(image_url, context)
        
        # Construir metadatos
        metadata = {"image_url": image_url}
        if page_number is not None:
            metadata["page_number"] = page_number
        
        return Chunk(
            document_id=doc_id,
            content=f"Análisis visual de imagen:\n{description}",
            type="image",
            metadata=metadata
        )