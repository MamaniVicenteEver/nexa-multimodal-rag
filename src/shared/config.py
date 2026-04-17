from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    NEXA_ROLE: str = "all"
    LOG_LEVEL: str = "INFO"

    REDIS_DSN: str = "redis://localhost:6379"
    # Reemplazamos Host/Port por Path
    CHROMA_PATH: str = "./data/chroma_db"
    VECTOR_STORE_BACKEND: str = "chromadb"
    STORAGE_BACKEND: str = "local"
    OCR_PROVIDER: str = "deepseek"

    NOVITA_API_KEY: str = ""
    NOVITA_BASE_URL: str = "https://api.novita.ai/openai"
    NOVITA_OCR_MODEL: str = "deepseek/deepseek-ocr-2"

    GEMINI_API_KEY: str = ""
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-2-preview"

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_CHAT_MODEL: str = "deepseek-chat"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/nexa_db"
# ...
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()