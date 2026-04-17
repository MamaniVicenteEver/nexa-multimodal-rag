# Arquitectura de Infraestructura — Nexa Multimodal RAG (v1.0)

**Autor:** Ever Mamani Vicente  
**Contacto:** evermamanivicente@gmail.com  
**Fecha:** Abril 2026  
**Estado:** Aprobado para desarrollo

> Este documento describe la arquitectura de infraestructura del sistema Nexa: como se organiza el codigo, como se despliega, como escala, como sobrevive a fallos y como evoluciona sin reescribir la logica de negocio. Para entender el motor RAG en si (flujos, entidades, agentes), consultar ENGINE.md.

---

## Tabla de Contenidos

1. [Principios Arquitectonicos](#1-principios-arquitectonicos)
2. [Estructura de Carpetas](#2-estructura-de-carpetas)
3. [Capa de Dominio y Puertos](#3-capa-de-dominio-y-puertos)
4. [Capa de Infraestructura (Adaptadores)](#4-capa-de-infraestructura-adaptadores)
5. [Modulos Funcionales](#5-modulos-funcionales)
6. [Punto de Entrada y Roles de Instancia](#6-punto-de-entrada-y-roles-de-instancia)
7. [Almacenamiento: Estrategia Local y en Nube](#7-almacenamiento-estrategia-local-y-en-nube)
8. [Cola de Tareas con Redis Streams](#8-cola-de-tareas-con-redis-streams)
9. [Configuracion y Variables de Entorno](#9-configuracion-y-variables-de-entorno)
10. [Despliegue con Docker y Kubernetes](#10-despliegue-con-docker-y-kubernetes)
11. [Escalabilidad Horizontal](#11-escalabilidad-horizontal)
12. [Estrategias de Resiliencia](#12-estrategias-de-resiliencia)
13. [Migracion a Microservicios](#13-migracion-a-microservicios)
14. [Observabilidad y Monitoreo](#14-observabilidad-y-monitoreo)
15. [Glosario](#15-glosario)

---

## 1. Principios Arquitectonicos

Cada decision de infraestructura en Nexa obedece a un conjunto de principios que deben mantenerse incluso cuando el sistema crezca. Estos principios son no negociables: cualquier propuesta de cambio que los viole requiere una justificacion documentada en los ADR (Architecture Decision Records).

**Inversion de Dependencias (DIP)**: Los modulos de alto nivel (casos de uso) no dependen de modulos de bajo nivel (bases de datos, APIs externas). Ambos dependen de abstracciones definidas en puertos (interfaces). Esto permite cambiar cualquier tecnologia de infraestructura sin tocar la logica de negocio.

**Arquitectura Hexagonal (Puertos y Adaptadores)**: El nucleo de negocio es un hexagono rodeado de adaptadores. Hacia adentro del hexagono: logica pura, entidades, casos de uso, agentes. Hacia afuera: implementaciones concretas que traducen entre el mundo externo y el nucleo.

**CQRS (Command Query Responsibility Segregation)**: Las operaciones de escritura (ingesta, actualizacion de estado) y las de lectura (busqueda, consulta de estado) tienen caminos separados. Esto permite optimizar cada camino de forma independiente y, eventualmente, usar bases de datos distintas para cada uno.

**Arquitectura orientada a eventos (EDA)**: Los cambios de estado se propagan mediante eventos. Un documento procesado genera un evento que actualiza el estado en Redis. Esto desacopla los componentes y facilita la transicion a microservicios.

**Monolito Modular como punto de partida**: El sistema se despliega como una sola unidad pero internamente esta dividido en modulos con limites bien definidos y sin dependencias circulares. Esta organizacion permite extraer cualquier modulo como microservicio sin reescritura.

**Statelessness en la capa web**: Los nodos de API no guardan estado local. Todo el estado reside en sistemas externos compartidos (Redis, bases de datos). Cualquier nodo puede atender cualquier peticion en cualquier momento.

**Resiliencia como requisito de primera clase**: El sistema debe seguir funcionando, aunque sea en modo degradado, ante fallos de servicios externos, saturacion de la cola o caidas parciales.

---

## 2. Estructura de Carpetas

La estructura esta disenada para que cada concepto viva exactamente donde se esperaria encontrarlo, para que agregar una nueva funcionalidad no requiera tocar mas de dos o tres archivos existentes, y para que eliminar una funcionalidad no deje referencias huerfanas.

```
nexa/
|
|-- docker/
|   |-- Dockerfile                         # Imagen unica multi-rol
|   |-- docker-compose.yml                 # Entorno de desarrollo completo
|   |-- docker-compose.prod.yml            # Configuracion base para produccion
|   `-- kubernetes/ (ESTO SOLO SERA IMPLEMENTADO UNA VEZ QUE LO REQUIERA LA ESCALA)
|       |-- base/
|       |   |-- deployment-api.yaml        # Deployment para el rol API
|       |   |-- deployment-worker.yaml     # Deployment para workers
|       |   |-- deployment-agent.yaml      # Deployment para el runtime de agentes
|       |   |-- service.yaml               # Service interno del cluster
|       |   |-- ingress.yaml               # Ingress con TLS
|       |   |-- hpa-api.yaml               # HPA para el rol API
|       |   |-- hpa-worker.yaml            # HPA para workers (basado en longitud de cola)
|       |   |-- configmap.yaml             # Variables no secretas
|       |   `-- secrets.yaml               # Secretos (referenciados desde Vault o similar)
|       |-- overlays/
|       |   |-- development/               # Ajustes para entorno de desarrollo
|       |   |-- staging/                   # Ajustes para staging
|       |   `-- production/                # Ajustes para produccion
|       `-- keda/
|           `-- scaled-object-worker.yaml  # KEDA ScaledObject para escalar workers por cola
|
|-- docs/
|   |-- README.md
|   |-- INFRASTRUCTURE.md                  # Este documento
|   |-- ENGINE.md
|   |-- ROADMAP.md
|   `-- adr/
|       |-- 001-monolito-modular.md
|       |-- 002-deepseek-ocr-vs-mistral.md
|       |-- 003-redis-streams-vs-rabbitmq.md
|       |-- 004-chromadb-vs-weaviate.md
|       `-- 005-almacenamiento-r2-vs-s3.md
|
|-- scripts/
|   |-- entrypoint.sh                      # Arranque segun NEXA_ROLE
|   |-- migrate_db.py                      # Migraciones de esquema
|   |-- seed_bm25.py                       # Reconstruccion del indice BM25 desde ChromaDB
|   `-- health_check.sh                    # Script de health check para Docker
|
|-- src/
|   |
|   |-- core/                              # NUCLEO DE NEGOCIO (cero dependencias externas)
|   |   |
|   |   |-- domain/                        # Entidades y value objects del dominio
|   |   |   |-- __init__.py
|   |   |   |-- document.py                # Document, DocumentStatus
|   |   |   |-- chunk.py                   # Chunk, ChunkType
|   |   |   |-- session.py                 # Session, ConversationTurn
|   |   |   |-- query.py                   # Query, ParsedIntent
|   |   |   |-- agent_task.py              # AgentTask, TaskStatus
|   |   |   `-- events.py                  # Eventos de dominio: DocumentProcessed, etc.
|   |   |
|   |   |-- ports/                         # Interfaces abstractas (contratos)
|   |   |   |-- __init__.py
|   |   |   |-- ocr_provider.py            # IOCRProvider
|   |   |   |-- vision_provider.py         # IVisionProvider
|   |   |   |-- embedding_provider.py      # IEmbeddingProvider
|   |   |   |-- vector_store.py            # IVectorStore
|   |   |   |-- lexical_index.py           # ILexicalIndex
|   |   |   |-- reranker.py                # IReranker
|   |   |   |-- llm_client.py              # ILLMClient
|   |   |   |-- queue.py                   # IQueue (publicar y consumir mensajes)
|   |   |   |-- state_repository.py        # IStateRepository (estado rapido)
|   |   |   |-- session_repository.py      # ISessionRepository
|   |   |   `-- file_storage.py            # IFileStorage (local, R2, GCS)
|   |   |
|   |   |-- use_cases/                     # Casos de uso: la logica de la aplicacion
|   |   |   |-- __init__.py
|   |   |   |-- ingest_document.py         # IngestDocumentUseCase
|   |   |   |-- process_document.py        # ProcessDocumentUseCase (ejecutado por worker)
|   |   |   |-- search_query.py            # SearchQueryUseCase
|   |   |   |-- get_document_status.py     # GetDocumentStatusUseCase
|   |   |   |-- manage_session.py          # CreateSession, GetSession, UpdateSession
|   |   |   `-- validate_response.py       # ValidateResponseUseCase (anti-alucinacion)
|   |   |
|   |   `-- agents/                        # Definicion de agentes (ADK 2.0)
|   |       |-- __init__.py
|   |       |-- supervisor.py              # Agente supervisor principal (Nexus)
|   |       |-- rag_agent.py               # Agente de recuperacion (Atlas)
|   |       |-- ingestion_agent.py         # Agente de ingesta (Forge)
|   |       |-- validator_agent.py         # Agente validador (Sentinel)
|   |       `-- tools/                     # Herramientas disponibles para los agentes
|   |           |-- search_tools.py        # search_documents, search_by_filters
|   |           |-- ingest_tools.py        # ingest_document, get_ingest_status
|   |           |-- session_tools.py       # get_session_context, update_active_document
|   |           `-- utility_tools.py       # ask_clarification, answer_general
|   |
|   |-- infrastructure/                    # IMPLEMENTACIONES CONCRETAS DE PUERTOS
|   |   |
|   |   |-- ocr/
|   |   |   |-- deepseek_adapter.py        # DeepSeek-OCR 2 via Novita AI
|   |   |   `-- docling_adapter.py         # Docling local (fallback sin costo)
|   |   |
|   |   |-- vision/
|   |   |   `-- gemini_flash_lite_adapter.py   # Descripcion de imagenes
|   |   |
|   |   |-- embeddings/
|   |   |   `-- gemini_embedding_adapter.py    # gemini-embedding-2-preview
|   |   |
|   |   |-- vector_stores/
|   |   |   |-- chromadb_adapter.py        # ChromaDB local o remoto
|   |   |   `-- vertex_ai_vector_adapter.py    # Vertex AI Vector Search (nube)
|   |   |
|   |   |-- lexical/
|   |   |   `-- bm25_adapter.py            # rank-bm25
|   |   |
|   |   |-- rerankers/
|   |   |   `-- bge_reranker_adapter.py    # BAAI/bge-reranker-v2-m3
|   |   |
|   |   |-- llm/
|   |   |   |-- deepseek_llm_adapter.py    # DeepSeek-V3.2 generador final
|   |   |   `-- gemini_llm_adapter.py      # Gemini 3.1 Pro / Flash-Lite
|   |   |
|   |   |-- queue/
|   |   |   `-- redis_streams_adapter.py   # Redis Streams con grupos de consumidores
|   |   |
|   |   |-- state/
|   |   |   `-- redis_state_adapter.py     # Estado rapido con TTL
|   |   |
|   |   |-- sessions/
|   |   |   |-- redis_session_adapter.py   # Sesiones activas (cache caliente)
|   |   |   `-- mongodb_session_adapter.py # Persistencia historica de sesiones
|   |   |
|   |   `-- storage/
|   |       |-- local_storage_adapter.py   # Sistema de archivos local
|   |       |-- r2_storage_adapter.py      # Cloudflare R2 (imagenes en nube)
|   |       `-- gcs_storage_adapter.py     # Google Cloud Storage (alternativa)
|   |
|   |-- modules/                           # MODULOS FUNCIONALES (empaquetan puertos + logica)
|   |   |
|   |   |-- ingestion/                     # Modulo de ingesta (comandos)
|   |   |   |-- __init__.py
|   |   |   |-- router.py                  # POST /v1/ingest, GET /v1/ingest/{id}/status
|   |   |   |-- service.py                 # Orquestacion: valida, encola, responde
|   |   |   |-- worker.py                  # Consumidor de cola: OCR, chunking, embeddings
|   |   |   |-- chunker.py                 # Logica de chunking semantico
|   |   |   |-- image_enricher.py          # Enriquecimiento de imagenes con vision LLM
|   |   |   `-- schemas.py                 # Pydantic schemas de request/response
|   |   |
|   |   |-- search/                        # Modulo de busqueda (consultas)
|   |   |   |-- __init__.py
|   |   |   |-- router.py                  # POST /v1/query
|   |   |   |-- service.py                 # Orquestacion: self-query, dual retrieval, rerank
|   |   |   |-- hybrid_retriever.py        # Fusion RRF de resultados vectoriales y lexicos
|   |   |   |-- prompt_assembler.py        # Ensamblado del prompt final con historial
|   |   |   `-- schemas.py
|   |   |
|   |   |-- sessions/                      # Modulo de sesiones
|   |   |   |-- __init__.py
|   |   |   |-- router.py                  # POST, GET, DELETE /v1/sessions
|   |   |   |-- service.py
|   |   |   `-- schemas.py
|   |   |
|   |   |-- agents/                        # Modulo del runtime de agentes ADK 2.0
|   |   |   |-- __init__.py
|   |   |   |-- router.py                  # POST /v1/agent/chat (interfaz principal)
|   |   |   |-- runner.py                  # Inicializacion y ejecucion de agentes
|   |   |   `-- callbacks.py               # Hooks de streaming y auditoria
|   |   |
|   |   `-- admin/                         # Modulo de administracion
|   |       |-- __init__.py
|   |       |-- router.py                  # GET /health, GET /metrics, POST /admin/reload
|   |       `-- health.py                  # Verificacion de dependencias externas
|   |
|   |-- lib/                            # CODIGO COMPARTIDO (sin dependencias de modulos)
|   |   |-- config.py                      # Settings con pydantic-settings
|   |   |-- logging.py                     # Configuracion de logs estructurados JSON
|   |   |-- exceptions.py                  # Excepciones de dominio y aplicacion
|   |   |-- middlewares.py                 # Rate limiting, request ID, tracing headers
|   |   |-- container.py                   # Contenedor de inyeccion de dependencias
|   |   `-- utils.py                       # Hash de archivos, conversion de unidades, etc.
|   |
|   `-- main.py                            # Punto de entrada unico (segun NEXA_ROLE)
|
|-- tests/
|   |-- unit/
|   |   |-- core/                          # Tests de casos de uso y entidades
|   |   |-- infrastructure/                # Tests de adaptadores con mocks
|   |   `-- modules/                       # Tests de servicios de modulos
|   |-- integration/
|   |   |-- test_ingestion_pipeline.py     # OCR real + ChromaDB en contenedor de prueba
|   |   `-- test_search_pipeline.py        # Busqueda hibrida con datos reales
|   `-- e2e/
|       `-- test_full_conversation.py      # Conversacion completa de extremo a extremo
|
|-- .env.example
|-- pyproject.toml
|-- Makefile
`-- README.md
```

### Principios que gobiernan esta estructura

**Una sola direccion de dependencias**: `main.py` -> `modules/` -> `core/` -> `ports/`. La infraestructura implementa los puertos pero nunca es importada por el nucleo. Las dependencias circulares son un error de compilacion.

**Modulos cerrados**: Un modulo no importa directamente de otro modulo. Si el modulo de busqueda necesita crear una sesion, lo hace a traves del puerto `ISessionRepository`, no importando de `modules/sessions/service.py`.

**Facilidad de extension**: Agregar un nuevo proveedor de OCR requiere crear un archivo en `infrastructure/ocr/` y registrarlo en `lib/container.py`. Nada mas cambia.

**Facilidad de eliminacion**: Eliminar el soporte para MongoDB requiere borrar `infrastructure/sessions/mongodb_session_adapter.py` y cambiar una linea en el contenedor. No hay referencias dispersas.

---

## 3. Capa de Dominio y Puertos

El directorio `src/core/` contiene todo lo que el sistema hace, sin preocuparse de como lo hace. No hay importaciones de bibliotecas de infraestructura aqui. Solo Python puro, dataclasses y protocolos.

### Entidades del dominio

Las entidades son la representacion del conocimiento del negocio. Son inmutables en lo posible y no contienen logica de persistencia.

```python
# src/core/domain/document.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid

class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"

@dataclass
class Document:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_filename: str = ""
    original_url: Optional[str] = None
    content_hash: Optional[str] = None       # SHA-256 para deduplicacion
    status: DocumentStatus = DocumentStatus.PENDING
    pages: int = 0
    chunks_count: int = 0
    chunk_ids: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    instruction: Optional[str] = None        # Contexto adicional del usuario al ingestar
```

### Puertos (interfaces)

Los puertos son contratos que la infraestructura debe cumplir. Se definen como clases abstractas o protocolos de Python.

```python
# src/core/ports/ocr_provider.py

from abc import ABC, abstractmethod
from typing import List
from core.domain.chunk import Chunk

class IOCRProvider(ABC):
    @abstractmethod
    async def extract(
        self,
        file_bytes: bytes,
        file_type: str,
        instruction: str = ""
    ) -> List[Chunk]:
        """
        Extrae el contenido estructurado de un documento.
        Devuelve una lista de chunks (texto, imagenes, tablas).
        """
        ...
```

```python
# src/core/ports/vector_store.py

from abc import ABC, abstractmethod
from typing import List, Optional
from core.domain.chunk import Chunk

class IVectorStore(ABC):
    @abstractmethod
    async def upsert(self, chunks: List[Chunk]) -> None: ...

    @abstractmethod
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 20,
        filters: Optional[dict] = None
    ) -> List[Chunk]: ...

    @abstractmethod
    async def delete_by_document(self, document_id: str) -> None: ...

    @abstractmethod
    async def health_check(self) -> bool: ...
```

---

## 4. Capa de Infraestructura (Adaptadores)

Cada adaptador implementa exactamente un puerto. La logica de traduccion entre el mundo externo y las entidades del dominio vive aqui. El nucleo nunca ve JSON de terceros, solo entidades propias.

### Ejemplo: Adaptador de DeepSeek-OCR 2

```python
# src/infrastructure/ocr/deepseek_adapter.py

import httpx
import base64
from typing import List
from core.ports.ocr_provider import IOCRProvider
from core.domain.chunk import Chunk, ChunkType
from lib.config import settings

class DeepSeekOCRAdapter(IOCRProvider):

    def __init__(self):
        self.api_key = settings.NOVITA_API_KEY
        self.base_url = "https://api.novita.ai/v3/openai"
        self.model = "deepseek/deepseek-ocr-2"

    async def extract(
        self,
        file_bytes: bytes,
        file_type: str,
        instruction: str = ""
    ) -> List[Chunk]:
        img_b64 = base64.b64encode(file_bytes).decode()
        prompt = f"<|grounding|>Convert this document page to Markdown."
        if instruction:
            prompt += f" Context: {instruction}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": f"data:image/png;base64,{img_b64}"},
                            {"type": "text", "text": prompt}
                        ]
                    }]
                }
            )
        markdown = response.json()["choices"][0]["message"]["content"]
        return self._parse_markdown_to_chunks(markdown)

    def _parse_markdown_to_chunks(self, markdown: str) -> List[Chunk]:
        # Aqui se separan los bloques de texto, imagenes y tablas
        # y se construyen entidades Chunk para cada uno
        ...
```

### Inyeccion de dependencias

El contenedor de dependencias registra que implementacion concreta usar para cada puerto. Cambiar de proveedor de OCR es una sola linea:

```python
# src/lib/container.py

from lib.config import settings
from core.ports.ocr_provider import IOCRProvider
from infrastructure.ocr.deepseek_adapter import DeepSeekOCRAdapter
from infrastructure.ocr.docling_adapter import DoclingAdapter

def get_ocr_provider() -> IOCRProvider:
    if settings.OCR_PROVIDER == "deepseek":
        return DeepSeekOCRAdapter()
    elif settings.OCR_PROVIDER == "docling":
        return DoclingAdapter()
    raise ValueError(f"OCR provider desconocido: {settings.OCR_PROVIDER}")
```

---

## 5. Modulos Funcionales

Cada modulo agrupa un endpoint (o conjunto de endpoints relacionados), su servicio de orquestacion, sus schemas Pydantic y cualquier logica especifica que no pertenezca al nucleo.

### Modulo de Ingesta

El modulo de ingesta recibe documentos, los valida, los encola y devuelve un `document_id` de forma inmediata. No espera a que el procesamiento termine.

El worker (definido en `modules/ingestion/worker.py`) consume la cola y ejecuta el caso de uso `ProcessDocumentUseCase`, que a su vez coordina OCR, chunking, enriquecimiento de imagenes, generacion de embeddings y almacenamiento dual.

### Modulo de Busqueda

El modulo de busqueda recibe una pregunta, invoca el self-querying para estructurarla, ejecuta la recuperacion hibrida, aplica el re-ranking y coordina la generacion de la respuesta. Opera de forma sincrona con soporte para streaming SSE.

### Modulo de Agentes

El modulo de agentes expone el endpoint principal de conversacion (`/v1/agent/chat`) y gestiona el ciclo de vida del agente supervisor (Nexus). Este modulo es el punto de entrada para interacciones complejas donde el sistema debe decidir autonomamente entre buscar, ingestar o responder directamente.

---

## 6. Punto de Entrada y Roles de Instancia

El archivo `src/main.py` es el unico punto de entrada. La variable de entorno `NEXA_ROLE` determina que componentes inicializa:

```python
# src/main.py

import os
import asyncio
from lib.config import settings

role = os.environ.get("NEXA_ROLE", "all")

if role in ("api", "all"):
    from modules.ingestion.router import router as ingestion_router
    from modules.search.router import router as search_router
    from modules.sessions.router import router as sessions_router
    from modules.agents.router import router as agents_router
    from modules.admin.router import router as admin_router
    # Registrar routers en la app FastAPI

if role in ("worker", "all"):
    from modules.ingestion.worker import start_worker
    asyncio.create_task(start_worker())

if role in ("agent", "all"):
    from modules.agents.runner import start_agent_runtime
    asyncio.create_task(start_agent_runtime())
```

Este diseno permite que Kubernetes ejecute pods especializados para cada rol, con escalado independiente basado en la carga de cada componente.

---

## 7. Almacenamiento: Estrategia Local y en Nube

El sistema maneja tres tipos de activos que requieren almacenamiento persistente: archivos originales (PDFs, imagenes), archivos de trabajo (imagenes extraidas de documentos) y vectores. La estrategia difiere segun el entorno de despliegue.

### Entorno Local (Desarrollo y On-Premise)

Todo se almacena localmente. No hay dependencias de servicios de nube.

**Archivos originales y extraidos**: Sistema de archivos local, montado como volumen persistente en Docker o Kubernetes. La ruta se configura con `LOCAL_STORAGE_PATH`.

**Vectores**: ChromaDB en modo local, persistiendo en un volumen de disco.

**Estado y cola**: Redis ejecutandose como contenedor.

**Sesiones historicas**: MongoDB ejecutandose como contenedor (opcional; Redis es suficiente para sesiones activas).

Levantar todo el entorno local requiere un solo comando:

```bash
docker compose up -d
```

El archivo `docker-compose.yml` define: Redis, ChromaDB, MongoDB y el propio servicio Nexa con los tres roles en un solo contenedor.

### Entorno en Nube (Produccion Escalable)

En nube, cada tipo de activo tiene su servicio optimo:

**Imagenes y documentos originales: Cloudflare R2**

Cloudflare R2 es compatible con la API de S3 pero sin costo de egreso. Las imagenes extraidas de documentos se convierten a formato WebP antes de almacenarse, reduciendo el tamano entre un 25% y un 35% sin perdida de calidad visual. El adaptador `R2StorageAdapter` maneja la conversion y el upload de forma transparente.

```
Costo estimado R2:
- Almacenamiento: $0.015 / GB / mes
- Operaciones de clase A (PUT): $4.50 / millon
- Operaciones de clase B (GET): $0.36 / millon
- Egreso: $0.00 (cero costo de salida)
```

La URL publica de cada imagen se genera con un dominio personalizado sobre R2, compatible con CDN de Cloudflare.

**Vectores: Vertex AI Vector Search**

Para despliegues de produccion a escala, Vertex AI Vector Search ofrece busqueda de proximidad de alta velocidad con SLA garantizado. El adaptador `VertexAIVectorAdapter` implementa el mismo puerto `IVectorStore` que ChromaDB, por lo que el cambio es transparente para el resto del sistema.

```
Costo estimado Vertex AI Vector Search:
- Almacenamiento de vectores: ~$0.10 / GB / hora (varia segun la configuracion)
- Consultas: ~$0.20 / millon de consultas
- Recomendacion: Evaluar el volumen de vectores antes de activar; ChromaDB en un
  servidor dedicado puede ser suficiente hasta los 50 millones de vectores.
```

**Estado y cola: Redis gestionado (Redis Cloud o Google Memorystore)**

Un Redis gestionado elimina la sobrecarga operativa de mantenimiento, actualizaciones y backups.

**Sesiones historicas: MongoDB Atlas o Firestore**

Para persistencia de sesiones a largo plazo en nube, MongoDB Atlas o Firestore ofrecen escalado automatico sin gestion de infraestructura.

### Seleccion del backend de almacenamiento

La variable `STORAGE_BACKEND` controla que adaptador se instancia:

```
STORAGE_BACKEND=local   -> LocalStorageAdapter
STORAGE_BACKEND=r2      -> R2StorageAdapter
STORAGE_BACKEND=gcs     -> GCSStorageAdapter
```

El contenedor de dependencias instancia el adaptador correcto en el arranque. Ningun caso de uso sabe donde viven fisicamente los archivos.

---

## 8. Cola de Tareas con Redis Streams

Redis Streams es el mecanismo de cola de tareas del sistema. Se eligio sobre RabbitMQ y SQS porque Redis ya esta en el stack para cache y estado, eliminar una dependencia externa reduce latencia y costos, y Redis Streams ofrece grupos de consumidores, confirmaciones de entrega (ACK) y reclamacion de mensajes caidos.

### Flujo de una tarea de ingesta

```
1. API recibe documento y crea entrada en Redis con estado PENDING
2. API publica mensaje en el stream ingest:tasks
3. Worker lee el mensaje con XREADGROUP (bloqueante, espera si no hay mensajes)
4. Worker actualiza estado a PROCESSING
5. Worker ejecuta OCR, chunking, embeddings, almacenamiento
6. Worker actualiza estado a READY (o FAILED con mensaje de error)
7. Worker confirma el mensaje con XACK
   -> Si el worker muere antes de XACK, el mensaje queda sin confirmar
   -> Otro worker lo reclamara con XCLAIM despues del timeout configurado
```

### Garantias de entrega

Ninguna tarea se pierde aunque el worker muera en mitad del procesamiento. El mecanismo de reclamacion asegura que tareas sin confirmar sean retomadas por otro worker. Si una tarea falla tres veces consecutivas, se mueve a una cola de errores (`ingest:failed`) para revision manual.

### Backpressure

Si la longitud del stream supera el 80% de `QUEUE_MAXLEN`, el endpoint de ingesta devuelve `429 Too Many Requests` con un header `Retry-After` calculado en funcion de la tasa actual de procesamiento.

---

## 9. Configuracion y Variables de Entorno

Toda la configuracion se centraliza en `src/lib/config.py` usando `pydantic-settings`. Las variables de entorno se validan al arranque; si una variable requerida falta, el sistema falla con un mensaje claro antes de procesar ninguna peticion.

| Variable | Tipo | Default | Recargable | Descripcion |
|----------|------|---------|-----------|-------------|
| `NEXA_ROLE` | str | `all` | No | Rol de la instancia |
| `NOVITA_API_KEY` | str | - | No | Clave API DeepSeek-OCR 2 |
| `GEMINI_API_KEY` | str | - | No | Clave API Google Gemini |
| `DEEPSEEK_API_KEY` | str | - | No | Clave API DeepSeek-V3.2 |
| `REDIS_DSN` | str | `redis://localhost:6379` | No | URI Redis |
| `CHROMA_HOST` | str | `localhost` | No | Host ChromaDB |
| `CHROMA_PORT` | int | `8001` | No | Puerto ChromaDB |
| `MONGODB_URI` | str | - | No | URI MongoDB (opcional) |
| `OCR_PROVIDER` | str | `deepseek` | No | Motor OCR activo |
| `VECTOR_STORE_BACKEND` | str | `chromadb` | No | Backend vectorial |
| `STORAGE_BACKEND` | str | `local` | No | Backend de archivos |
| `LOCAL_STORAGE_PATH` | str | `/data/storage` | No | Ruta local de archivos |
| `R2_ACCOUNT_ID` | str | - | No | Cuenta Cloudflare R2 |
| `R2_ACCESS_KEY` | str | - | No | Clave acceso R2 |
| `R2_SECRET_KEY` | str | - | No | Clave secreta R2 |
| `R2_BUCKET_NAME` | str | `nexa-storage` | No | Bucket R2 |
| `WORKER_CONCURRENCY` | int | `5` | Si | Workers por pod |
| `QUEUE_MAXLEN` | int | `10000` | Si | Tamano maximo de cola |
| `MAX_PAGES_PER_DOCUMENT` | int | `1000` | Si | Limite de paginas |
| `MAX_DOCUMENTS_PER_REQUEST` | int | `10` | Si | Documentos por peticion |
| `CIRCUIT_BREAKER_FAIL_MAX` | int | `5` | Si | Fallos para abrir circuito |
| `CIRCUIT_BREAKER_TIMEOUT` | int | `30` | Si | Segundos con circuito abierto |
| `CHUNK_MAX_TOKENS` | int | `1000` | Si | Tokens maximos por chunk |
| `TOP_K_RETRIEVAL` | int | `20` | Si | Candidatos por busqueda |
| `TOP_K_RERANK` | int | `5` | Si | Resultados tras re-ranking |
| `SESSION_TTL_SECONDS` | int | `86400` | Si | TTL de sesiones en Redis |
| `LOG_LEVEL` | str | `INFO` | Si | Nivel de log |
| `ENABLE_RESPONSE_VALIDATION` | bool | `true` | Si | Activar agente validador |

Las variables marcadas como recargables pueden actualizarse en tiempo de ejecucion llamando a `POST /admin/reload` sin reiniciar el proceso.

---

## 10. Despliegue con Docker y Kubernetes

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema (necesarias para PyMuPDF y similares)
RUN apt-get update && apt-get install -y \
    libmupdf-dev \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install -e ".[prod]" --no-cache-dir

COPY src/ ./src/
COPY scripts/ ./scripts/

ENV PYTHONPATH=/app/src
EXPOSE 8000

ENTRYPOINT ["sh", "scripts/entrypoint.sh"]
```

```bash
# scripts/entrypoint.sh
#!/bin/sh

case "$NEXA_ROLE" in
  api)
    exec uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1
    ;;
  worker)
    exec python src/main.py --role worker
    ;;
  agent)
    exec python src/main.py --role agent
    ;;
  all)
    # Modo desarrollo: todo en un proceso
    exec python src/main.py --role all
    ;;
esac
```

### docker-compose.yml (desarrollo local)

```yaml
version: "3.9"

services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  chromadb:
    image: chromadb/chroma:latest
    ports: ["8001:8000"]
    volumes:
      - chroma_data:/chroma/chroma

  mongodb:
    image: mongo:7
    ports: ["27017:27017"]
    volumes:
      - mongo_data:/data/db

  nexa:
    build: .
    ports: ["8000:8000"]
    environment:
      NEXA_ROLE: all
      REDIS_DSN: redis://redis:6379
      CHROMA_HOST: chromadb
      MONGODB_URI: mongodb://mongodb:27017/nexa
    env_file: .env
    depends_on: [redis, chromadb, mongodb]
    volumes:
      - ./data:/data/storage

volumes:
  redis_data:
  chroma_data:
  mongo_data:
```

### Kubernetes: Despliegue multi-rol

En produccion, cada rol corre en su propio Deployment con su propio HPA:

```yaml
# kubernetes/base/deployment-api.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nexa-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: nexa
      role: api
  template:
    metadata:
      labels:
        app: nexa
        role: api
    spec:
      containers:
      - name: nexa
        image: nexa:latest
        env:
        - name: NEXA_ROLE
          value: "api"
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
```

```yaml
# kubernetes/keda/scaled-object-worker.yaml
# Escala workers en funcion de la longitud de la cola Redis
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: nexa-worker-scaler
spec:
  scaleTargetRef:
    name: nexa-worker
  minReplicaCount: 1
  maxReplicaCount: 20
  triggers:
  - type: redis-streams
    metadata:
      address: redis:6379
      stream: ingest:tasks
      consumerGroup: nexa-workers
      pendingEntriesCount: "50"   # 1 worker por cada 50 mensajes pendientes
```

---

## 11. Escalabilidad Horizontal

El sistema escala sin coordinacion entre instancias porque no hay estado compartido en los pods.

**Capa API**: Escala por CPU y peticiones por segundo. El HPA agrega replicas cuando la CPU supera el 70% durante mas de dos minutos consecutivos. Un balanceador de carga distribuye peticiones round-robin.

**Capa Worker**: Escala por longitud de cola. KEDA observa el stream de Redis y agrega o elimina replicas de workers segun los mensajes pendientes. El escalado es rapido (menos de 30 segundos para agregar un worker).

**Capa Agente**: Escala por CPU y numero de sesiones activas. El agente supervisor es stateless: el estado de cada sesion vive en Redis.

**Estado compartido**: Redis (estado de documentos, sesiones, cola), ChromaDB o Vertex AI (vectores), almacenamiento de archivos (local compartido o R2). Estos servicios son el unico cuello de botella de escalado, y deben desplegarse en modo de alta disponibilidad en produccion.

---

## 12. Estrategias de Resiliencia

### Circuit Breaker

Cada llamada a un servicio externo (DeepSeek-OCR, Gemini, Redis) esta protegida por un circuit breaker implementado con `pybreaker`.

```python
from pybreaker import CircuitBreaker, CircuitBreakerError

ocr_breaker = CircuitBreaker(
    fail_max=settings.CIRCUIT_BREAKER_FAIL_MAX,
    reset_timeout=settings.CIRCUIT_BREAKER_TIMEOUT
)

class DeepSeekOCRAdapter(IOCRProvider):
    @ocr_breaker
    async def extract(self, file_bytes, file_type, instruction=""):
        # Si esto falla CIRCUIT_BREAKER_FAIL_MAX veces consecutivas,
        # el circuito se abre y las llamadas siguientes fallan inmediatamente
        # hasta que CIRCUIT_BREAKER_TIMEOUT segundos hayan pasado
        ...
```

Cuando el circuito hacia DeepSeek-OCR se abre, el sistema activa automaticamente el fallback a Docling local. La calidad puede ser menor, pero el servicio sigue operativo.

### Reintentos con backoff exponencial

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=16)
)
async def call_gemini_vision(image_bytes, prompt):
    # Primer intento inmediato, luego 1s, 2s, 4s antes de renunciar
    ...
```

### Modo degradado automatico

Si la carga del sistema supera un umbral (medida como longitud de cola + CPU de workers), el sistema entra en modo degradado automaticamente:

- El enriquecimiento de imagenes con Gemini se desactiva temporalmente. Las imagenes se indexan sin descripcion.
- El re-ranking se reduce de top-40 a top-20 candidatos.
- El validador de respuestas se desactiva.

El sistema sale del modo degradado automaticamente cuando las metricas vuelven al rango normal.

### Garantias de la cola

Los mensajes sin confirmar (ACK) se reclaman automaticamente despues de un timeout configurable. Si un worker muere procesando un documento, otro worker retomara la tarea desde el principio. La idempotencia del pipeline (basada en el hash del contenido del documento) asegura que reprocesar un documento no genera duplicados.

### Tablon de fallos

| Componente en falla | Comportamiento del sistema |
|--------------------|---------------------------|
| DeepSeek-OCR 2 | Fallback a Docling local; calidad reducida pero servicio activo |
| Gemini (embeddings) | Cola de ingesta se pausa; reintentos automaticos con backoff |
| ChromaDB | Busqueda devuelve solo resultados BM25; se advierte al usuario |
| Redis (estado) | API devuelve 503; workers pausan consumo |
| Redis (cola) | API rechaza nuevas ingestas con 503; ingestas en curso continuan |
| MongoDB | Sesiones historicas no disponibles; sesiones activas en Redis siguen funcionando |
| Almacenamiento de archivos | Ingesta de nuevos documentos falla; busquedas sobre documentos existentes funcionan |

---

## 13. Migracion a Microservicios

La arquitectura hexagonal garantiza que extraer cualquier modulo como microservicio sea una operacion de infraestructura, no de logica de negocio.

### Proceso de extraccion de un modulo

El proceso es el mismo para cualquier modulo:

1. El modulo seleccionado (por ejemplo, el servicio de OCR) se mueve a un repositorio separado.
2. Se crea un nuevo adaptador en `infrastructure/ocr/` que llama al microservicio via HTTP en lugar de ejecutarlo localmente.
3. El contenedor de dependencias apunta al nuevo adaptador segun una variable de entorno.
4. El nucleo (`core/`) no cambia ni una linea.

```python
# infrastructure/ocr/remote_ocr_adapter.py
# Nuevo adaptador que llama al microservicio de OCR

import httpx
from core.ports.ocr_provider import IOCRProvider
from core.domain.chunk import Chunk
from typing import List

class RemoteOCRAdapter(IOCRProvider):
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def extract(
        self,
        file_bytes: bytes,
        file_type: str,
        instruction: str = ""
    ) -> List[Chunk]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/extract",
                files={"file": file_bytes},
                data={"file_type": file_type, "instruction": instruction}
            )
            response.raise_for_status()
            return [Chunk(**c) for c in response.json()["chunks"]]
```

### Orden recomendado de extraccion

Cuando el volumen justifique la complejidad operativa de microservicios, la secuencia de extraccion recomendada es:

1. Servicio de OCR (alto consumo de CPU, escala de forma independiente al resto)
2. Servicio de Embeddings (las llamadas a Gemini pueden agruparse en batch)
3. Servicio de busqueda hibrida (puede convertirse en API de busqueda reutilizable)
4. Servicio de agentes (el runtime de ADK puede alojar multiples agentes)

---

## 14. Observabilidad y Monitoreo

### Metricas Prometheus

El endpoint `/metrics` expone metricas en formato Prometheus:

```
nexa_documents_ingested_total          # Contador de documentos procesados
nexa_documents_failed_total            # Contador de fallos de ingesta
nexa_ingest_queue_length               # Longitud actual de la cola
nexa_ingest_duration_seconds           # Histograma de duracion de ingesta
nexa_ocr_latency_seconds               # Latencia de llamadas al OCR
nexa_embedding_latency_seconds         # Latencia de generacion de embeddings
nexa_search_latency_seconds            # Latencia total de una busqueda
nexa_circuit_breaker_state{service}    # Estado del circuit breaker (0=cerrado, 1=abierto)
nexa_active_sessions                   # Sesiones activas en Redis
nexa_worker_active                     # Workers activos por pod
```

### Trazas distribuidas

Cada peticion lleva un `X-Request-ID` que se propaga a todas las llamadas internas y externas. OpenTelemetry exporta las trazas a Jaeger (en desarrollo) o Google Cloud Trace (en produccion).

### Logs estructurados

Todos los logs son JSON con los campos: `timestamp`, `level`, `request_id`, `doc_id`, `session_id`, `module`, `step`, `duration_ms`, `message`.

---

## 15. Glosario

**ADR (Architecture Decision Record)**: Documento que registra una decision arquitectonica importante, su contexto, las alternativas consideradas y la justificacion de la eleccion.

**Adaptador**: Implementacion concreta de un puerto. Traduce entre el mundo externo y las entidades del dominio.

**Circuit Breaker**: Patron que evita llamadas repetidas a un servicio que esta fallando, permitiendo que el sistema se recupere sin sobrecargarlo.

**CQRS**: Command Query Responsibility Segregation. Separacion de operaciones de escritura y lectura.

**EDA**: Event-Driven Architecture. Arquitectura donde los componentes se comunican mediante eventos.

**KEDA**: Kubernetes Event-Driven Autoscaling. Extension de Kubernetes para escalar basandose en eventos externos como la longitud de una cola.

**Monolito Modular**: Un sistema que se despliega como una sola unidad pero esta organizado internamente en modulos con limites bien definidos.

**Puerto (Port)**: Interfaz abstracta en el nucleo de negocio que define un contrato de comportamiento sin especificar la implementacion.

**RRF (Reciprocal Rank Fusion)**: Formula para combinar rankings de distintas fuentes de busqueda: `score = sum(1 / (k + rank))`.

**Stateless**: Caracteristica de un componente que no guarda estado entre peticiones. Permite escalar horizontalmente sin coordinacion.