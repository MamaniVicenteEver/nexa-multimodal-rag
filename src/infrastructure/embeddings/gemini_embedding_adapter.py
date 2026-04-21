import time
from typing import List
from google import genai
from src.core.ports.embedding_provider import IEmbeddingProvider
from src.shared.config import settings
from src.shared.logging import get_logger

logger = get_logger("gemini_embedding")

class GeminiEmbeddingAdapter(IEmbeddingProvider):
    def __init__(self, max_batch_size: int = 100):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_EMBEDDING_MODEL
        self.max_batch_size = max_batch_size   # API permite hasta 100 textos por llamada
        self.max_retries = 3
        self.retry_delay = 1.0

    def embed_text(self, text: str) -> List[float]:
        """Mantiene compatibilidad con llamadas individuales."""
        if not text or not text.strip():
            return [0.0] * 3072
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Genera embeddings para una lista de textos en una o varias llamadas HTTP.
        """
        if not texts:
            return []

        all_embeddings = []
        for i in range(0, len(texts), self.max_batch_size):
            batch = texts[i:i + self.max_batch_size]
            batch_embeddings = self._embed_batch_with_retry(batch)
            all_embeddings.extend(batch_embeddings)
            
        logger.info(f"Generados embeddings para {len(texts)} textos en {len(all_embeddings) // self.max_batch_size} lotes.")
        return all_embeddings

    def _embed_batch_with_retry(self, texts: List[str]) -> List[List[float]]:
        """Lógica de reintentos para un lote concreto."""
        for attempt in range(self.max_retries):
            try:
                result = self.client.models.embed_content(
                    model=self.model,
                    contents=texts,          # ← aquí se envía la lista completa
                    config={"output_dimensionality": 3072}
                )
                if not result or not result.embeddings:
                    raise ValueError("Respuesta vacía de la API")
                return [emb.values for emb in result.embeddings]
            except Exception as e:
                logger.warning(f"Intento {attempt+1}/{self.max_retries} falló para lote: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise RuntimeError(f"No se pudo generar embeddings para lote: {e}")