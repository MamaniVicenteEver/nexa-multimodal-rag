from google import genai
from typing import List
from src.core.ports.embedding_provider import IEmbeddingProvider
from src.shared.config import settings

class GeminiEmbeddingAdapter(IEmbeddingProvider):
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_EMBEDDING_MODEL

    def embed_text(self, text: str) -> List[float]:
        result = self.client.models.embed_content(
            model=self.model,
            contents=[text]
        )
        return result.embeddings[0].values