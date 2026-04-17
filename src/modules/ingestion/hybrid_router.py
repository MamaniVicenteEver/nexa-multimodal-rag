import fitz  # PyMuPDF
from src.core.ports.ocr_provider import IOCRProvider
from src.shared.logging import get_logger

logger = get_logger("hybrid_router")

class HybridDocumentProcessor:
    def __init__(self, visual_ocr_adapter: IOCRProvider):
        self.visual_ocr = visual_ocr_adapter

    async def process_pdf(self, pdf_bytes: bytes, doc_id: str) -> str:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        extracted_markdown_parts = []
        total_pages = len(doc)
        
        logger.info("Iniciando enrutamiento híbrido", extra={"doc_id": doc_id, "total_pages": total_pages})

        pages_sent_to_api = 0
        pages_processed_locally = 0

        for page_num in range(total_pages):
            page = doc[page_num]

            has_images = len(page.get_images(full=True)) > 0
            has_vector_drawings = len(page.get_drawings()) > 0
            text_content = page.get_text("text").strip()
            
            is_complex_page = has_images or has_vector_drawings or len(text_content) < 50

            if is_complex_page:
                logger.debug(f"Página {page_num + 1} enrutada a DeepSeek-OCR (Compleja)")
                pages_sent_to_api += 1
                
                # CORRECCIÓN: Forzamos alpha=False para eliminar transparencias que rompen la API
                # Usamos PNG para evitar pérdida de calidad en texto pequeño
                pix = page.get_pixmap(dpi=150, alpha=False)
                image_bytes = pix.tobytes("png")

                try:
                    md_text = await self.visual_ocr.extract(image_bytes)
                    extracted_markdown_parts.append(f"\n\n\n\n{md_text}")
                except Exception as e:
                    logger.error(f"Fallo el OCR Visual en la página {page_num + 1}", exc_info=True)
                    extracted_markdown_parts.append(f"\n\n")
            else:
                logger.debug(f"Página {page_num + 1} enrutada a PyMuPDF (Texto simple)")
                pages_processed_locally += 1
                extracted_markdown_parts.append(f"\n\n\n\n{text_content}")

        doc.close()
        
        logger.info(
            "Análisis de PDF completado", 
            extra={
                "doc_id": doc_id, 
                "pages_local": pages_processed_locally, 
                "pages_api": pages_sent_to_api,
                "api_savings_percentage": round((pages_processed_locally / total_pages) * 100, 2) if total_pages > 0 else 0
            }
        )

        return "".join(extracted_markdown_parts)