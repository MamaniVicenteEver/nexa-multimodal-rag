from openai import AsyncOpenAI
import base64
from src.core.ports.ocr_provider import IOCRProvider
from src.shared.config import settings

class DeepSeekOCRAdapter(IOCRProvider):
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.NOVITA_API_KEY, 
            base_url=settings.NOVITA_BASE_URL
        )
        self.model = settings.NOVITA_OCR_MODEL

    async def extract(self, file_bytes: bytes) -> str:
        # Codificación segura utf-8
        img_b64 = base64.b64encode(file_bytes).decode('utf-8')
        
        # Estructura estricta para wrappers compatibles con OpenAI Vision
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Extract the text, tables, and structural layout from this document page and output it as Markdown."
                        },
                        {
                            "type": "image_url", 
                            "image_url": {
                                "url": f"data:image/png;base64,{img_b64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=4096,
            temperature=0.0 # Temperatura 0 para OCR determinista
        )
        
        return response.choices[0].message.content