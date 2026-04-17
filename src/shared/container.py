from src.infrastructure.database.postgres_adapter import PostgresRepositoryAdapter
from src.core.ports.database_repository import IDatabaseRepository
from src.shared.config import settings
from src.core.ports.ocr_provider import IOCRProvider
from src.core.ports.file_storage import IFileStorage
from src.core.ports.embedding_provider import IEmbeddingProvider
from src.core.ports.vector_store import IVectorStore
from src.core.ports.llm_client import ILLMClient

from src.infrastructure.ocr.deepseek_adapter import DeepSeekOCRAdapter
from src.infrastructure.embeddings.gemini_embedding_adapter import GeminiEmbeddingAdapter
from src.infrastructure.vector_stores.chromadb_adapter import ChromaDBAdapter
from src.infrastructure.llm.deepseek_llm_adapter import DeepSeekLLMAdapter
from src.infrastructure.storage.local_storage_adapter import LocalStorageAdapter

class Container:
    # Patrón Singleton perezoso para las instancias compartidas
    _ocr_provider: IOCRProvider = None
    _embedding_provider: IEmbeddingProvider = None
    _vector_store: IVectorStore = None
    _llm_client: ILLMClient = None
    _file_storage: IFileStorage = None
    _database_repository: IDatabaseRepository = None

    @classmethod
    def get_ocr_provider(cls) -> IOCRProvider:
        if cls._ocr_provider is None:
            # CORRECTO: Evaluamos el proveedor interno, no el modelo de la API
            if settings.OCR_PROVIDER == "deepseek":
                cls._ocr_provider = DeepSeekOCRAdapter()
            elif settings.OCR_PROVIDER == "docling":
                # cls._ocr_provider = DoclingAdapter() # Para el futuro
                pass
            else:
                raise ValueError(f"OCR Provider {settings.OCR_PROVIDER} not supported.")
        return cls._ocr_provider

    @classmethod
    def get_embedding_provider(cls) -> IEmbeddingProvider:
        if cls._embedding_provider is None:
            cls._embedding_provider = GeminiEmbeddingAdapter()
        return cls._embedding_provider

    @classmethod
    def get_vector_store(cls) -> IVectorStore:
        if cls._vector_store is None:
            if settings.VECTOR_STORE_BACKEND == "chromadb":
                cls._vector_store = ChromaDBAdapter()
            else:
                raise ValueError("Vector store not supported.")
        return cls._vector_store

    @classmethod
    def get_llm_client(cls) -> ILLMClient:
        if cls._llm_client is None:
            cls._llm_client = DeepSeekLLMAdapter()
        return cls._llm_client
    
    @classmethod
    def get_storage_provider(cls) -> IFileStorage:
        if cls._file_storage is None:
            if settings.STORAGE_BACKEND == "local":
                cls._file_storage = LocalStorageAdapter()
            else:
                raise ValueError(f"Storage Backend {settings.STORAGE_BACKEND} no soportado.")
        return cls._file_storage
    
    @classmethod
    def get_database_repository(cls) -> IDatabaseRepository:
        if cls._database_repository is None:
            cls._database_repository = PostgresRepositoryAdapter()
        return cls._database_repository