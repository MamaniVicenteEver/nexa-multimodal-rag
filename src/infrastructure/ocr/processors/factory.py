"""
Fábrica para obtener el procesador de páginas adecuado según configuración.
"""

from src.core.ports.page_processor import IPageProcessor
from src.shared.config import settings
from src.infrastructure.ocr.processors.local_processor import LocalPageProcessor
from src.infrastructure.ocr.processors.mistral_processor import MistralPageProcessor
from src.infrastructure.ocr.processors.deepseek_processor import DeepSeekPageProcessor
from src.shared.logging import get_logger

logger = get_logger("processor_factory")


def get_page_processor() -> IPageProcessor:
    """
    Devuelve una instancia del procesador de páginas configurado.

    La configuración se toma de settings.OCR_PROVIDER:
        - "local"   -> LocalPageProcessor (gratuito, PyMuPDF)
        - "mistral" -> MistralPageProcessor
        - "deepseek"-> DeepSeekPageProcessor

    Raises:
        ValueError: Si el proveedor no es soportado.
    """
    provider = settings.OCR_PROVIDER.lower()

    if provider == "local":
        logger.info("Usando procesador LOCAL (PyMuPDF)")
        return LocalPageProcessor()

    elif provider == "mistral":
        logger.info("Usando procesador MISTRAL OCR")
        return MistralPageProcessor()

    elif provider == "deepseek":
        logger.info("Usando procesador DEEPSEEK OCR")
        return DeepSeekPageProcessor()

    else:
        raise ValueError(f"OCR_PROVIDER '{provider}' no soportado. Use 'local', 'mistral' o 'deepseek'.")