from asyncio.log import logger
from src.modules.search.service import SearchOrchestrator
from src.core.ports.vision_provider import IVisionProvider
from src.infrastructure.vision.gemini_flash_lite_adapter import GeminiFlashLiteVisionAdapter
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
from src.infrastructure.ocr.mistral_adapter import MistralOCRAdapter

class Container:
    # Patrón Singleton perezoso para las instancias compartidas
    _ocr_provider: IOCRProvider = None
    _embedding_provider: IEmbeddingProvider = None
    _vector_store: IVectorStore = None
    _llm_client: ILLMClient = None
    _file_storage: IFileStorage = None
    _database_repository: IDatabaseRepository = None
    _vision_provider: IVisionProvider = None
    _search_orchestrator: SearchOrchestrator = None 

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
    
    @classmethod
    def get_ocr_provider(cls) -> IOCRProvider:
        if cls._ocr_provider is None:
            provider = settings.OCR_PROVIDER.lower()
            
            if provider == "deepseek":
                logger.info("Iniciando motor OCR: DeepSeek")
                cls._ocr_provider = DeepSeekOCRAdapter()
            
            elif provider == "mistral":
                logger.info("Iniciando motor OCR: Mistral")
                cls._ocr_provider = MistralOCRAdapter()
                
            else:
                raise ValueError(f"OCR Provider '{provider}' no soportado.")
                
        return cls._ocr_provider
    
    @classmethod
    def get_vision_provider(cls):
        if cls._vision_provider is None:
            # Aquí podrías usar una variable de entorno como VISION_PROVIDER="gemini"
            # si tuvieras más de un modelo en el futuro.
            logger.info("Iniciando motor de Visión: Gemini Flash-Lite")
            cls._vision_provider = GeminiFlashLiteVisionAdapter()
        return cls._vision_provider

    @classmethod
    def get_search_orchestrator(cls) -> SearchOrchestrator:
        if cls._search_orchestrator is None:
            cls._search_orchestrator = SearchOrchestrator(
                vector_store=cls.get_vector_store(),
                embed_adapter=cls.get_embedding_provider(),  # <-- Antes era embed_provider
                llm_client=cls.get_llm_client(),
                db_adapter=cls.get_database_repository()
            )
        return cls._search_orchestrator