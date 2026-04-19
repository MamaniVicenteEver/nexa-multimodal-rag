"""
Contrato (interfaz) que cualquier procesador de páginas debe implementar.

POR QUÉ EXISTE ESTA INTERFAZ:
  El sistema necesita poder cambiar entre Mistral, DeepSeek, un futuro modelo
  de texto barato, o incluso PyMuPDF puro, sin que el orquestador
  (HybridDocumentProcessor) sepa ni le importe cuál está usando.
  Esta interfaz es el "enchufe": define la forma del conector, no quién lo fabrica.

POR QUÉ process_pages RECIBE page_indices Y NO LAS PÁGINAS YA ABIERTAS:
  Cada procesador tiene necesidades distintas:
    - Mistral necesita el PDF completo en bytes para enviarlo a su API.
    - DeepSeek necesita rasterizar cada página individualmente.
    - Un procesador local necesita abrir el PDF con fitz.
  Si pasáramos fitz.Page directamente, acoplaríamos a todos con PyMuPDF.
  Con pdf_bytes + page_indices, cada procesador decide cómo abrir y usar el PDF.

POR QUÉ DEVUELVE dict[int, tuple[str, list[str]]]:
  - La clave int es el índice de página original (0-based).
    El orquestador necesita saber a qué página corresponde cada resultado
    para ensamblar el Markdown final en el orden correcto.
  - El str es el Markdown de esa página (con tablas e imágenes ya integradas).
  - El list[str] son las URLs locales de imágenes extraídas.
    Para Mistral estas URLs ya están en el Markdown; para DeepSeek se añaden aparte.
    El orquestador decide qué hacer con ellas según el proveedor.
"""


from abc import ABC, abstractmethod
from typing import List, Tuple, Dict


class IPageProcessor(ABC):
    """
    Procesador de páginas específicas de un PDF.

    Cada implementación concreta sabe cómo comunicarse con su backend
    (local, Mistral, DeepSeek) y devuelve el contenido Markdown junto
    con las URLs de las imágenes extraídas.
    """

    @abstractmethod
    async def process_pages(
        self,
        pdf_bytes: bytes,
        page_indices: List[int],
        doc_id: str,
    ) -> Dict[int, Tuple[str, List[str]]]:
        """
        Procesa las páginas indicadas del PDF.

        Args:
            pdf_bytes: Contenido completo del PDF en bytes.
            page_indices: Lista de índices de página (0‑based) a procesar.
            doc_id: Identificador único del documento (para guardar debug).

        Returns:
            Diccionario donde:
                - clave: índice de página (int)
                - valor: tupla (markdown_text, list_of_image_urls)

            Las páginas no procesadas o fallidas pueden omitirse del dict;
            el orquestador se encargará del fallback.
        """
        pass