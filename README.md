# Nexa Multimodal RAG

> Motor de recuperacion aumentada por generacion (RAG) multimodal, disenado para procesar documentos complejos, mantener conversaciones con memoria y escalar desde un monolito modular hasta una arquitectura de microservicios sin reescribir la logica de negocio.

---

## Indice

- [Vision del Proyecto](#vision-del-proyecto)
- [Casos de Uso Objetivo](#casos-de-uso-objetivo)
- [Caracteristicas Principales](#caracteristicas-principales)
- [Stack Tecnologico](#stack-tecnologico)
- [Arquitectura en una Linea](#arquitectura-en-una-linea)
- [Estructura del Repositorio](#estructura-del-repositorio)
- [Inicio Rapido (Local)](#inicio-rapido-local)
- [Variables de Entorno](#variables-de-entorno)
- [Endpoints Principales](#endpoints-principales)
- [Principios de Diseno](#principios-de-diseno)
- [Documentacion Tecnica](#documentacion-tecnica)
- [Estado del Proyecto](#estado-del-proyecto)
- [Autor](#autor)

---

## Vision del Proyecto

Nexa nace como un motor de inteligencia documental que puede adaptarse a multiples verticales de negocio. En su forma mas basica, es una plataforma que permite a cualquier usuario cargar documentos y conversar con ellos. En su forma mas avanzada, es el cerebro detras de agentes de ventas automatizados, asistentes especializados por industria y sistemas de recuperacion de conocimiento institucional.

El principio rector es simple: **los mejores resultados posibles al menor costo de infraestructura posible**, compitiendo en calidad con sistemas de grandes corporaciones mediante una seleccion inteligente de modelos, estrategias hibridas de recuperacion y una arquitectura que elimina el desperdicio en cada capa.

---

## Casos de Uso Objetivo

**Plataforma de analisis documental**: Cualquier usuario puede subir contratos, informes, manuales tecnicos o estados financieros y hacer preguntas en lenguaje natural. El sistema responde citando la fuente exacta dentro del documento.

**Motor de ventas conversacional**: Una tienda conecta su catalogo de productos. Un agente entrenado sobre ese catalogo responde a clientes con precision, ofrece alternativas, explica caracteristicas y cierra ventas, sin que el cliente distinga si habla con una persona o con el sistema.

**Base de conocimiento institucional**: Empresas indexan su documentacion interna (procesos, politicas, historiales de proyectos) y sus equipos consultan en lenguaje natural, con respuestas auditables y trazables hasta la pagina de origen.

**Integrador de verticales**: Al tratarse de un motor desacoplado, puede servir como backend para aplicaciones web, bots de mensajeria, interfaces de voz o cualquier canal que consuma la API REST.

---

## Caracteristicas Principales

**Ingesta multimodal asincrona**: Acepta PDF, Word, imagenes y texto plano. Devuelve un `document_id` de forma inmediata y procesa en segundo plano sin bloquear al cliente.

**OCR de alta fidelidad**: Utiliza DeepSeek-OCR 2 para extraer texto, tablas y layout con una precision del 91% en benchmarks estandar, a un costo de $0.03 por millon de tokens, frente a los $2.00 de alternativas equivalentes.

**Chunking semantico con enriquecimiento de imagenes**: Las imagenes no se descartan. Se describen automaticamente con contexto circundante mediante Gemini Flash-Lite y se indexan como cualquier otro fragmento de texto.

**Recuperacion hibrida (Dual Retrieval)**: Combina busqueda vectorial (ChromaDB) con busqueda lexica exacta (BM25). Ningun termino tecnico se pierde por no tener equivalente semantico en los embeddings.

**Re-ranking con cross-encoder**: Antes de generar la respuesta, los candidatos recuperados pasan por un modelo de re-clasificacion que evalua cada par (pregunta, fragmento) conjuntamente, elevando la precision sin aumentar la latencia de forma significativa.

**Memoria de conversacion**: Cada sesion recuerda el documento activo, el historial de turnos y las preferencias del usuario. El agente supervisor infiere referencias implicitas ("del mismo documento...") sin que el usuario repita identificadores.

**Arquitectura stateless y escalable**: Ningun nodo guarda estado local. Todo el estado reside en Redis y las bases de datos externas. Un pod puede eliminarse en cualquier momento sin perdida de datos ni interrupcion del servicio.

**Preparado para microservicios**: Cada modulo interno puede extraerse como servicio independiente cambiando un adaptador. La logica de negocio central no requiere modificacion.

---

## Stack Tecnologico

| Capa | Tecnologia | Funcion |
|------|-----------|---------|
| API | FastAPI + Pydantic | Endpoints REST asincronos con validacion estricta |
| OCR | DeepSeek-OCR 2 (Novita AI) | Extraccion estructural de documentos complejos |
| Vision | Gemini 3.1 Flash-Lite | Descripcion de imagenes y enriquecimiento semantico |
| Embeddings | Gemini Embedding 2 Preview | Vectorizacion de 3072 dimensiones |
| Vector Store | ChromaDB | Busqueda semantica por similitud |
| Busqueda lexica | BM25 (rank-bm25) | Busqueda por terminos exactos |
| Re-ranking | BGE-reranker-v2-m3 (HuggingFace) | Clasificacion de precision entre pregunta y fragmento |
| Generacion | DeepSeek-V3.2 | Sintesis de respuesta final |
| Supervisor | Gemini 3.1 Pro (via ADK 2.0) | Orquestacion de agentes y razonamiento de alto nivel |
| Cola de tareas | Redis Streams | Procesamiento asincrono con garantias de entrega |
| Estado y cache | Redis | Sesiones, embeddings cacheados, estado de documentos |
| Persistencia historica | MongoDB (opcional) | Almacenamiento de sesiones a largo plazo |
| Orquestacion de agentes | Google ADK 2.0 | Framework de agentes con herramientas y razonamiento |
| Observabilidad | OpenTelemetry + Prometheus | Trazas distribuidas y metricas de produccion |

---

## Arquitectura en una Linea

```
Cliente -> API Gateway (FastAPI) -> Cola (Redis Streams) -> Workers
                                -> Agente Supervisor (ADK 2.0) -> RAG Agent -> ChromaDB + BM25
                                                                             -> DeepSeek-V3.2
```

El sistema opera con tres roles diferenciados que pueden ejecutarse en el mismo contenedor o en pods separados: `api`, `worker` y `agent`. La variable de entorno `NEXA_ROLE` controla el comportamiento de cada instancia.

---

## Estructura del Repositorio

```
nexa/
├── src/
│   ├── core/                   # Logica de negocio pura (sin infraestructura)
│   │   ├── domain/             # Entidades: Document, Chunk, Session, Query
│   │   ├── ports/              # Interfaces abstractas (IOCRProvider, IVectorStore...)
│   │   ├── use_cases/          # Casos de uso: IngestDocument, SearchQuery...
│   │   └── agents/             # Definicion de agentes ADK 2.0
│   ├── infrastructure/         # Implementaciones concretas de los puertos
│   ├── modules/                # Modulos funcionales con sus endpoints y servicios
│   └── shared/                 # Configuracion, logging, excepciones, middlewares
├── tests/
├── docker/
│   └── kubernetes/
├── docs/
│   ├── README.md               # Este documento
│   ├── INFRASTRUCTURE.md       # Arquitectura, despliegue y escalabilidad
│   ├── ENGINE.md               # Motor RAG: flujos, entidades, agentes, estrategias
│   └── ROADMAP.md              # Plan de construccion por objetivos
├── scripts/
├── .env.example
├── pyproject.toml
└── Makefile
```

---

## Inicio Rapido (Local)

**Requisitos previos**: Docker, Docker Compose, Python 3.11+, Node.js 18+ (solo para herramientas de desarrollo).

```bash
# 1. Clonar el repositorio
git clone https://github.com/usuario/nexa-rag.git
cd nexa-rag

# 2. Copiar y configurar variables de entorno
cp .env.example .env
# Editar .env con las claves de API correspondientes

# 3. Levantar infraestructura local (Redis, ChromaDB, MongoDB)
docker compose up -d redis chromadb mongodb

# 4. Instalar dependencias de Python
pip install -e ".[dev]"

# 5. Ejecutar migraciones iniciales
python scripts/migrate_db.py

# 6. Iniciar la API
NEXA_ROLE=api python src/main.py

# 7. En otra terminal, iniciar los workers
NEXA_ROLE=worker python src/main.py

# 8. En otra terminal, iniciar el runtime de agentes
NEXA_ROLE=agent python src/main.py
```

La API estara disponible en `http://localhost:8000`. La documentacion interactiva en `http://localhost:8000/docs`.

Para ejecutar el sistema completo en un solo proceso (modo desarrollo):

```bash
NEXA_ROLE=all python src/main.py
```

---

## Variables de Entorno

| Variable | Descripcion | Requerida |
|----------|-------------|-----------|
| `NOVITA_API_KEY` | Clave de API para DeepSeek-OCR 2 | Si |
| `GEMINI_API_KEY` | Clave de API para modelos Gemini | Si |
| `DEEPSEEK_API_KEY` | Clave de API para DeepSeek-V3.2 | Si |
| `REDIS_DSN` | URI de conexion a Redis | Si |
| `CHROMA_HOST` | Host de ChromaDB | Si |
| `MONGODB_URI` | URI de MongoDB (persistencia historica) | No |
| `NEXA_ROLE` | Rol de la instancia: `api`, `worker`, `agent`, `all` | Si |
| `OCR_PROVIDER` | Motor OCR: `deepseek` o `docling` | No (default: `deepseek`) |
| `WORKER_CONCURRENCY` | Workers en paralelo por pod | No (default: 5) |
| `LOG_LEVEL` | Nivel de log: `DEBUG`, `INFO`, `WARNING` | No (default: `INFO`) |
| `STORAGE_BACKEND` | Almacenamiento de archivos: `local`, `r2`, `gcs` | No (default: `local`) |
| `R2_ACCOUNT_ID` | ID de cuenta Cloudflare R2 (si aplica) | Condicional |
| `R2_ACCESS_KEY` | Clave de acceso R2 | Condicional |
| `R2_SECRET_KEY` | Clave secreta R2 | Condicional |

El archivo `.env.example` contiene todas las variables documentadas con sus valores por defecto y comentarios explicativos.

---

## Endpoints Principales

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `POST` | `/v1/ingest` | Subir uno o varios documentos para procesamiento asincrono |
| `GET` | `/v1/ingest/{doc_id}/status` | Consultar el estado de procesamiento de un documento |
| `POST` | `/v1/query` | Realizar una pregunta en lenguaje natural sobre documentos indexados |
| `POST` | `/v1/sessions` | Crear una nueva sesion de conversacion |
| `GET` | `/v1/sessions/{session_id}` | Recuperar el estado y el historial de una sesion |
| `DELETE` | `/v1/sessions/{session_id}` | Eliminar una sesion y limpiar su estado |
| `GET` | `/health` | Health check para balanceadores de carga |
| `GET` | `/metrics` | Metricas Prometheus |
| `POST` | `/admin/reload` | Recargar configuracion sin reiniciar (variables recargables) |

---

## Principios de Diseno

**Arquitectura Hexagonal**: El nucleo de negocio no conoce la infraestructura. Los puertos (interfaces) separan lo que el sistema hace de como lo hace.

**CQRS**: Los comandos (ingesta, modificacion) y las consultas (busqueda, lectura) tienen caminos separados, lo que permite optimizar cada uno de forma independiente.

**Statelessness**: Ningun nodo de la API almacena estado local. Esto permite escalar horizontalmente sin coordinacion entre instancias.

**Resiliencia por diseno**: Circuit breakers, reintentos con backoff exponencial, colas con garantias de entrega y modos degradados aseguran que el sistema siga funcionando ante fallos parciales.

**Configuracion como codigo**: Toda parametrizacion vive en archivos de entorno. Ciertos parametros pueden modificarse en tiempo de ejecucion sin reinicio.

---

## Documentacion Tecnica

| Documento | Contenido |
|-----------|-----------|
| [INFRASTRUCTURE.md](./INFRASTRUCTURE.md) | Arquitectura general, estructura de carpetas, Kubernetes, escalabilidad, resiliencia, migracion a microservicios |
| [ENGINE.md](./ENGINE.md) | Motor RAG: entidades, flujos detallados, agentes, estrategias de recuperacion, memoria, optimizacion |
| [ROADMAP.md](./ROADMAP.md) | Plan de construccion por objetivos, decisiones de almacenamiento, evolucion del sistema |

---

## Estado del Proyecto

El sistema se encuentra en fase de construccion activa. Consultar `ROADMAP.md` para conocer el objetivo actual, los completados y los proximos pasos.

---

## Autor

**Ever Mamani Vicente**  
Arquitecto de Software  
evermamanivicente@gmail.com


