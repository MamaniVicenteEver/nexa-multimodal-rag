import os
import asyncio
from google import genai
from src.core.ports.vision_provider import IVisionProvider
from src.shared.config import settings
from src.shared.logging import get_logger

logger = get_logger("gemini_vision")

class GeminiFlashLiteVisionAdapter(IVisionProvider):
    def __init__(self):
        # El nuevo SDK se inicializa mediante la clase Client
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = 'gemini-3.1-flash-lite-preview'

    async def describe_image(self, image_path: str, context: str) -> str:
        base_dir = os.getcwd()
        safe_path = image_path.lstrip('/') if image_path.startswith('/') else image_path
        full_path = os.path.join(base_dir, safe_path)

        if not os.path.exists(full_path):
            logger.error(f"Imagen física no encontrada en: {full_path}")
            return "*(Imagen no disponible para análisis)*"

        logger.debug(f"Cargando imagen desde disco: {full_path}")

        prompt = f"""
        Eres un analista de datos y documentos experto.
        Aquí tienes una imagen extraída de un documento y el texto que la rodeaba.
        Describe detalladamente los datos, gráficos, tablas o información clave visible en la imagen.
        Ignora lo que no sea relevante.

        --- CONTEXTO ADYACENTE DEL DOCUMENTO ---
        {context}
        ----------------------------------------
        
        Devuelve SOLO la descripción.
        """

        try:
            # 1. Subida de archivo (I/O Bound). 
            # Delegamos al thread pool para no bloquear FastAPI.
            sample_file = await asyncio.to_thread(
                self.client.files.upload, file=full_path
            )
            
            # 2. Generación asíncrona usando la nueva interfaz .aio
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[prompt, sample_file]
            )
            
            # 3. Limpieza de archivo (I/O Bound).
            await asyncio.to_thread(
                self.client.files.delete, name=sample_file.name
            )
            
            return response.text.strip()
            
        except Exception as e:
            logger.error("Error en la API de Gemini Vision (Nuevo SDK)", exc_info=True)
            return "*(Error al procesar la imagen con IA)*"