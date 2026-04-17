# ROADMAP.md
# Nexa Multimodal RAG — Plan de Construccion por Objetivos

**Autor:** Ever Mamani Vicente  
**Contacto:** evermamanivicente@gmail.com  
**Fecha:** Abril 2026

> Este documento es un plan de construccion vivo. Describe que se debe construir primero, por que en ese orden, y como se evoluciona el sistema de forma gradual sin romper lo que ya funciona. No esta organizado por dias ni semanas porque el ritmo de avance depende de pruebas, aprendizajes y decisiones que solo pueden tomarse en el proceso. Cada objetivo tiene un criterio de exito claro: si no se cumple, no se avanza al siguiente.

> **Sobre la adaptabilidad del roadmap**: Si durante el desarrollo de cualquier objetivo aparece una herramienta, modelo o estrategia que mejora significativamente el sistema (mejor calidad, menor costo o menor complejidad), el roadmap puede actualizarse. La seccion de cada objetivo incluye el punto exacto donde esa nueva herramienta podria integrarse y como evaluar si el cambio vale la pena.

---

## Indice

1. [Filosofia del Roadmap](#1-filosofia-del-roadmap)
2. [Mapa General de Objetivos](#2-mapa-general-de-objetivos)
3. [Objetivo 0: Fundamentos del Proyecto](#3-objetivo-0-fundamentos-del-proyecto)
4. [Objetivo 1: El Motor Minimo Funcional](#4-objetivo-1-el-motor-minimo-funcional)
5. [Objetivo 2: Multimodalidad Real](#5-objetivo-2-multimodalidad-real)
6. [Objetivo 3: Busqueda Hibrida Completa](#6-objetivo-3-busqueda-hibrida-completa)
7. [Objetivo 4: Memoria y Sesiones](#7-objetivo-4-memoria-y-sesiones)
8. [Objetivo 5: Sistema de Agentes](#8-objetivo-5-sistema-de-agentes)
9. [Objetivo 6: Resiliencia y Modo Degradado](#9-objetivo-6-resiliencia-y-modo-degradado)
10. [Objetivo 7: Almacenamiento en Nube](#10-objetivo-7-almacenamiento-en-nube)
11. [Objetivo 8: Despliegue en Kubernetes](#11-objetivo-8-despliegue-en-kubernetes)
12. [Objetivo 9: Primera Vertical de Negocio](#12-objetivo-9-primera-vertical-de-negocio)
13. [Objetivo 10: Escalado y Microservicios](#13-objetivo-10-escalado-y-microservicios)
14. [Decisiones de Almacenamiento en Detalle](#14-decisiones-de-almacenamiento-en-detalle)
15. [Criterios para Actualizar el Roadmap](#15-criterios-para-actualizar-el-roadmap)

---

## 1. Filosofia del Roadmap

**Construir el motor primero, equiparlo despues**: Un sistema RAG sin motor de recuperacion de calidad no tiene valor, independientemente de cuantas capas se agreguen encima. La prioridad absoluta es hacer que el ciclo ingesta -> busqueda -> respuesta funcione correctamente antes de agregar funcionalidades.

**Un objetivo completo es mejor que dos objetivos a medias**: Cada objetivo produce un sistema funcional y demostrable. No se inicia el siguiente hasta que el criterio de exito del actual este cumplido y documentado.

**La infraestructura sigue a la necesidad**: No se despliega Kubernetes antes de tener algo que desplegar. No se migra a Cloudflare R2 antes de tener documentos que almacenar. La infraestructura avanzada se agrega cuando el sistema la justifica, no antes.

**Las pruebas son parte del objetivo**: Un objetivo no esta completo si no tiene pruebas que verifiquen el criterio de exito. Las pruebas no son una fase separada al final; son la forma de confirmar que cada pieza funciona.

**Documentar lo que se decide**: Cada vez que se toma una decision de diseno significativa (elegir un modelo, cambiar una estrategia, descartar una tecnologia), se crea un ADR en `docs/adr/`. Esto protege al equipo futuro de repetir los mismos errores.

---

## 2. Mapa General de Objetivos

```
Objetivo 0   Fundamentos del proyecto
     |
     v
Objetivo 1   Motor minimo funcional (OCR + vector store + busqueda + generacion)
     |
     v
Objetivo 2   Multimodalidad real (imagenes enriquecidas, tablas indexadas)
     |
     v
Objetivo 3   Busqueda hibrida completa (BM25 + vectorial + RRF + reranking)
     |
     v
Objetivo 4   Memoria y sesiones (contexto de conversacion, referencias implicitas)
     |
     v
Objetivo 5   Sistema de agentes (Nexus, Atlas, Forge, Sentinel)
     |
     v
Objetivo 6   Resiliencia y modo degradado (circuit breakers, fallbacks, backpressure)
     |
     v
Objetivo 7   Almacenamiento en nube (R2, Vertex AI, Redis gestionado)
     |
     v
Objetivo 8   Despliegue en Kubernetes (multi-rol, HPA, KEDA, TLS)
     |
     v
Objetivo 9   Primera vertical de negocio (plataforma web o motor de ventas)
     |
     v
Objetivo 10  Escalado y extraccion de microservicios
```

Los objetivos son secuenciales hasta el 6. Los objetivos 7, 8 y 9 pueden comenzarse en paralelo una vez que el 6 este completo, ya que tienen dependencias independientes. El objetivo 10 depende de que el sistema tenga carga real que justifique la extraccion.

---

## 3. Objetivo 0: Fundamentos del Proyecto

### Que se construye

La estructura del repositorio, el entorno de desarrollo, las configuraciones base y los contratos de dominio. Nada que el usuario final vea, pero todo lo que hace posible construir lo demas sin caos.

### Tareas especificas

**Repositorio y herramientas**:
- Crear la estructura de carpetas definida en INFRASTRUCTURE.md.
- Configurar `pyproject.toml` con todas las dependencias de desarrollo y produccion.
- Crear `.env.example` con todas las variables documentadas.
- Crear `Makefile` con comandos estandarizados: `make dev`, `make test`, `make lint`, `make build`.
- Configurar pre-commit hooks: `black`, `isort`, `mypy`, `ruff`.

**Contenedor de desarrollo**:
- Crear `docker-compose.yml` con Redis, ChromaDB y MongoDB.
- Verificar que los tres servicios arrancan y responden al health check.
- Documentar el proceso de arranque en README.md.

**Entidades del dominio**:
- Implementar `Document`, `Chunk`, `Session`, `Query` con sus enums y value objects.
- Implementar todos los puertos (interfaces abstractas) definidos en `src/core/ports/`.
- Escribir pruebas unitarias para las entidades: validacion de estados, transiciones validas.

**Contenedor de inyeccion de dependencias**:
- Implementar `src/shared/container.py` con la logica de seleccion de adaptadores segun variables de entorno.
- Verificar que el contenedor puede instanciar cada adaptador correctamente.

**FastAPI base**:
- Crear `src/main.py` con la logica de arranque multi-rol.
- Registrar el modulo `admin` con el endpoint `/health` y `/metrics` (metricas vacias por ahora).

### Criterio de exito

El comando `make dev` levanta Redis, ChromaDB y MongoDB sin errores. El endpoint `GET /health` devuelve `{"status": "ok"}`. Las pruebas unitarias de dominio pasan al 100%. La estructura de carpetas coincide con la definida en INFRASTRUCTURE.md.

### Donde podria cambiar

Si aparece un framework de inyeccion de dependencias mejor que la implementacion manual (por ejemplo, `dependency-injector` de Python), puede reemplazar `container.py` en este objetivo sin afectar nada mas.

---

## 4. Objetivo 1: El Motor Minimo Funcional

### Que se construye

El ciclo completo mas simple posible: un PDF entra, se procesa con OCR, los fragmentos de texto se indexan en ChromaDB y se puede hacer una pregunta cuya respuesta se genera con DeepSeek-V3.2. Sin multimodalidad, sin BM25, sin agentes, sin sesiones. Solo el camino critico funcionando.

### Por que este orden

Antes de agregar precision (BM25, reranking) o funcionalidades (sesiones, agentes), hay que confirmar que el camino basico funciona correctamente. Un motor que procesa texto y responde preguntas sobre el, aunque sea de forma simple, ya tiene valor y ya puede probarse con usuarios reales.

### Tareas especificas

**Adaptador de OCR (DeepSeek-OCR 2)**:
- Implementar `DeepSeekOCRAdapter` que llama a la API de Novita.
- Manejar documentos de multiples paginas: procesar pagina por pagina.
- Manejar errores de red y timeouts (sin circuit breaker aun, solo `try/except` con log).
- Retornar una lista de chunks de tipo texto.

**Adaptador local de fallback (Docling)**:
- Implementar `DoclingAdapter` para procesamiento local sin costo.
- Seleccionable via `OCR_PROVIDER=docling` en el `.env`.

**Pipeline de chunking basico**:
- Implementar `chunker.py` en el modulo de ingesta con `RecursiveCharacterTextSplitter`.
- Configurar separadores jerarquicos y limite de 1000 tokens.
- Incluir solapamiento de 100 tokens entre chunks consecutivos.

**Adaptador de embeddings (Gemini Embedding 2)**:
- Implementar `GeminiEmbeddingAdapter`.
- Manejar el limite de tokens de la API (batching si el texto excede el limite).

**Adaptador de ChromaDB**:
- Implementar `ChromadbAdapter` con operaciones upsert y search.
- Configurar la coleccion con dimension 3072.
- Implementar `health_check()` para detectar si ChromaDB esta disponible.

**Cola con Redis Streams (version simplificada)**:
- Implementar `RedisStreamsAdapter` con operaciones de publicar y consumir.
- El worker consume mensajes con `XREADGROUP` bloqueante.
- ACK del mensaje al finalizar el procesamiento.
- Sin CLAIM de mensajes caidos en esta version (se agrega en Objetivo 6).

**Modulo de ingesta**:
- Implementar `POST /v1/ingest` que valida el archivo, crea el documento en Redis (estado PENDING) y publica en la cola.
- Implementar `GET /v1/ingest/{doc_id}/status` que lee el estado de Redis.
- Implementar el worker que consume la cola y ejecuta OCR + chunking + embeddings + ChromaDB.

**Adaptador de generacion (DeepSeek-V3.2)**:
- Implementar `DeepSeekLLMAdapter` que llama a la API de DeepSeek.
- Soporte para streaming SSE.

**Modulo de busqueda (version basica, solo vectorial)**:
- Implementar `POST /v1/query` sin self-querying: la pregunta se vectoriza directamente y se busca en ChromaDB.
- Sin BM25, sin reranking, sin sesiones.
- Devolver los 5 chunks mas similares y generar la respuesta.

**Pruebas de integracion**:
- Prueba que ingesta un PDF de prueba y verifica que el estado llega a READY.
- Prueba que hace una pregunta sobre el PDF ingestado y devuelve una respuesta con fuentes.

### Criterio de exito

Un PDF de 10 paginas puede ser ingestado y consultado. La pregunta "De que trata este documento?" devuelve una respuesta coherente con referencias a chunks especificos. El procesamiento completo de las 10 paginas tarda menos de 3 minutos.

### Donde podria cambiar

Si aparece un modelo de OCR mas economico y con calidad equivalente durante el desarrollo de este objetivo, es el momento de evaluarlo y actualizar `ADR-002`. Si ChromaDB presenta limitaciones inesperadas (por ejemplo, problemas de rendimiento con la dimension 3072), es el momento de evaluar `pgvector` como alternativa.

---

## 5. Objetivo 2: Multimodalidad Real

### Que se construye

El sistema aprende a procesar imagenes, graficos y tablas. Las imagenes extraidas de documentos se describen con Gemini Flash-Lite y se indexan como cualquier otro chunk. Las preguntas sobre graficos y elementos visuales comienzan a tener respuestas correctas.

### Por que este orden

La multimodalidad es uno de los diferenciadores principales de Nexa frente a sistemas RAG simples. Sin ella, el sistema ignora entre el 20% y el 40% del contenido informativo de documentos tecnicos o comerciales tipicos. Agregar multimodalidad antes de refinar la precision de busqueda (Objetivo 3) permite probar el enriquecimiento de imagenes con el camino de recuperacion mas simple y depurar errores en el proceso de descripcion.

### Tareas especificas

**Adaptador de vision (Gemini Flash-Lite)**:
- Implementar `GeminiFlashLiteVisionAdapter` que acepta imagen en Base64 + contexto textual.
- El prompt del sistema debe pedir una descripcion autocontenida de 50-200 palabras.
- Reintentos con backoff exponencial (1s, 2s, 4s) ante timeouts de la API.

**Enriquecedor de imagenes**:
- Implementar `image_enricher.py` en el modulo de ingesta.
- Algoritmo: detectar referencias a imagenes en el Markdown, extraer contexto anterior y posterior (hasta 500 caracteres cada uno), llamar al adaptador de vision, crear un chunk de tipo imagen con la descripcion como contenido.
- Almacenar la imagen fisica en el sistema de archivos local (ruta configurable).
- Guardar la URL de la imagen en el campo `image_url` del chunk.

**Conversion a WebP**:
- Antes de almacenar cualquier imagen, convertirla a WebP usando `Pillow`.
- Configurar calidad WebP en 85% (buen balance entre calidad visual y tamano).
- Log del tamano original vs tamano final para monitorear el ahorro.

**Chunking de tablas**:
- Detectar bloques de Markdown de tabla (patron `| col | col |`).
- Chunkizar tablas como unidades completas, nunca partidas a la mitad.
- Agregar `type = "table"` en los metadatos del chunk.
- Si una tabla excede 1000 tokens, dividirla por filas pero mantener la cabecera en cada subchunk.

**Chunking de formulas (opcional en este objetivo)**:
- Detectar bloques de LaTeX (`$$...$$` o `$...$`).
- Guardar como chunk de tipo `formula`.
- La descripcion de la formula se genera con Gemini Flash-Lite si es necesario.

**Actualizacion del worker de ingesta**:
- Despues del OCR y la limpieza, ejecutar el enriquecimiento de imagenes antes del chunking.
- El pipeline de imagenes puede ejecutarse en paralelo con el chunking de texto (asyncio.gather).

**Pruebas**:
- Prueba con un PDF que contenga al menos un grafico y una tabla.
- Verificar que el chunk de imagen tiene una descripcion coherente.
- Preguntar "que muestra el grafico de la pagina X" y verificar que la respuesta usa el chunk de imagen.

### Criterio de exito

Un documento con 5 imagenes y 3 tablas se indexa completamente. Las preguntas sobre el contenido de las imagenes son respondidas con informacion extraida de las descripciones generadas. Las tablas son recuperadas cuando la pregunta pide datos que estan en ellas.

### Donde podria cambiar

Si aparece un modelo de vision mas economico que Gemini Flash-Lite con calidad equivalente para descripcion de imagenes documentales, es el momento de actualizar el adaptador. La abstraccion `IVisionProvider` hace que el cambio no afecte al resto del sistema.

---

## 6. Objetivo 3: Busqueda Hibrida Completa

### Que se construye

Se agrega el self-querying estructurado, el indice BM25, la fusion RRF y el re-ranking con cross-encoder. Al final de este objetivo, el sistema tiene la mayor precision posible en recuperacion con la arquitectura disenada.

### Por que este orden

Con el motor basico y la multimodalidad funcionando, ya se puede medir la calidad de la recuperacion. En este objetivo se optimiza esa calidad aplicando las tres mejoras mas impactantes: self-querying (mejora la consulta), BM25 (captura terminos exactos que los embeddings pierden) y reranking (refina la seleccion final).

### Tareas especificas

**Self-querying con Gemini Flash-Lite**:
- Implementar el prompt de self-querying que extrae intencion semantica, palabras clave y filtros.
- El resultado debe ser JSON valido con los campos: `semantic_query`, `keywords`, `filters`, `language`.
- Manejar la posibilidad de que el modelo no devuelva JSON valido (fallback: usar la pregunta original como `semantic_query`).

**Indice BM25**:
- Implementar `BM25Adapter` usando la libreria `rank-bm25`.
- El indice se construye en memoria al arrancar el sistema, leyendo todos los chunks de texto desde ChromaDB.
- Implementar serializacion/deserializacion del indice en Redis o disco para no reconstruirlo en cada arranque.
- Implementar busqueda que acepta lista de keywords y devuelve chunks ordenados por relevancia lexica.

**Fusion RRF**:
- Implementar `hybrid_retriever.py` que toma los resultados de ChromaDB y BM25 y aplica la formula RRF.
- Parametro `k=60` como constante inicial (puede ajustarse con pruebas).
- Deduplicar chunks que aparecen en ambas listas antes de aplicar RRF.

**Re-ranking con BGE**:
- Descargar el modelo `BAAI/bge-reranker-v2-m3` de HuggingFace en el arranque.
- Implementar `BGERerankerAdapter` que acepta una pregunta y una lista de chunks y devuelve los chunks reordenados por puntuacion.
- El cross-encoder se ejecuta sobre los top-40 candidatos de la fusion RRF y devuelve los top-5.
- Medir la latencia del reranking con datos reales y ajustar si supera 500ms.

**Actualizacion del modulo de busqueda**:
- Reemplazar la busqueda directa a ChromaDB por el pipeline completo: self-query -> dual retrieval -> RRF -> reranking -> generacion.
- Actualizar los schemas de respuesta para incluir mas informacion de trazabilidad (chunk_id, tipo, pagina, puntuacion de reranking).

**Pruebas de calidad**:
- Preparar un conjunto de 20 preguntas de evaluacion con respuestas esperadas conocidas.
- Medir precision@5 (cuantos de los 5 chunks recuperados son relevantes) antes y despues del reranking.
- Documentar los resultados en `docs/evaluation/baseline_retrieval.md`.

### Criterio de exito

La busqueda hibrida recupera los chunks correctos para al menos el 85% de las preguntas del conjunto de evaluacion. El tiempo de respuesta total (desde la peticion hasta el inicio del streaming) es menor a 2 segundos para documentos ya indexados.

### Donde podria cambiar

Si el reranking con BGE-reranker-v2-m3 muestra latencia inaceptable en CPU (mas de 1 segundo para 40 pares), se puede evaluar Cohere Rerank como alternativa de API. El cambio es trivial gracias al puerto `IReranker`.

Si aparece un modelo de embeddings con mejor calidad en benchmarks de recuperacion documental, es el momento de evaluar el cambio y actualizar el indice. Esto requiere re-vectorizar todos los chunks existentes.

---

## 7. Objetivo 4: Memoria y Sesiones

### Que se construye

El sistema recuerda las conversaciones. Los usuarios pueden hacer preguntas de seguimiento sin repetir el contexto. El sistema infiere el documento activo de la sesion y aplica filtros automaticamente.

### Tareas especificas

**Adaptador de sesiones en Redis**:
- Implementar `RedisSessionAdapter` con operaciones create, get, update, delete.
- La sesion se serializa como JSON y se almacena con TTL configurable.
- El `active_document_id` se actualiza automaticamente cuando el usuario sube un documento.

**Inyeccion de historial en el prompt**:
- Modificar el prompt assembler para incluir los ultimos N turnos de la sesion.
- N configurable via variable de entorno (default: 5 turnos).
- Truncar el historial si excede el limite de tokens del contexto del modelo generador.

**Manejo de referencias implicitas**:
- Si `active_document_id` esta definido en la sesion y la pregunta no menciona un documento especifico, agregar el filtro automaticamente antes de ejecutar la busqueda.
- Si la pregunta menciona "el documento anterior" o construcciones similares, resolver la referencia usando el historial de la sesion.

**Persistencia historica (MongoDB, opcional)**:
- Implementar `MongoDBSessionAdapter` que guarda sesiones completadas en MongoDB.
- La sesion se mueve de Redis a MongoDB cuando su TTL expira o cuando el usuario la cierra explicitamente.
- Si MongoDB no esta disponible, la sesion simplemente expira en Redis sin error.

**Endpoints de sesion**:
- `POST /v1/sessions`: crear una nueva sesion.
- `GET /v1/sessions/{id}`: recuperar estado e historial.
- `DELETE /v1/sessions/{id}`: cerrar y persistir la sesion.

**Pruebas**:
- Conversacion de 5 turnos sobre el mismo documento, verificando que el sistema infiere el documento activo sin que el usuario lo mencione.
- Verificar que el historial no excede el limite de tokens al cabo de 10 turnos.

### Criterio de exito

Una conversacion de 5 turnos sobre un documento funciona correctamente, con cada respuesta informada por el historial previo. La referencia implicita "del mismo documento" resuelve correctamente al documento activo de la sesion.

---

## 8. Objetivo 5: Sistema de Agentes

### Que se construye

Los cuatro agentes del sistema: Nexus (supervisor), Atlas (recuperacion), Forge (ingesta) y Sentinel (validacion). El endpoint principal de conversacion `/v1/agent/chat` que centraliza todas las interacciones a traves del agente supervisor.

### Por que este orden

Los agentes son la capa de inteligencia de alto nivel que hace que el sistema sea capaz de manejar conversaciones complejas y ambiguas. Se construyen despues de que todos los componentes subyacentes (busqueda, ingesta, sesiones) esten funcionando, porque los agentes los orquestan pero no los reemplazan.

### Tareas especificas

**Instalacion y configuracion de ADK 2.0**:
- Instalar `google-adk==2.0` y verificar compatibilidad con el resto del stack.
- Configurar el modelo de Nexus (Gemini 3.1 Pro) con las credenciales de Vertex AI o Google AI.

**Implementacion de herramientas**:
- `search_tools.py`: implementar `search_documents` como `FunctionTool` que llama al caso de uso `SearchQueryUseCase`.
- `ingest_tools.py`: implementar `ingest_document` y `get_ingest_status` que llaman al modulo de ingesta.
- `session_tools.py`: implementar `update_active_document` y `get_session_context`.
- `utility_tools.py`: implementar `ask_clarification` y `answer_general`.

**Nexus (Supervisor)**:
- Definir el `LlmAgent` con la instruccion del supervisor descrita en ENGINE.md.
- Registrar todas las herramientas disponibles.
- Implementar la logica de contexto de sesion: pasar el `active_document_id` y el historial reciente como parte del contexto del agente.

**Atlas (Recuperacion)**:
- Definir como agente que orquesta el pipeline de busqueda hibrida.
- En esta primera implementacion, Atlas puede no ser un `LlmAgent` independiente sino un agente de pipeline que Nexus invoca directamente. La conversion a agente completo puede hacerse en el Objetivo 10.

**Forge (Ingesta)**:
- Similar a Atlas: puede comenzar como un agente de pipeline que encola la tarea y hace polling del estado.

**Sentinel (Validacion)**:
- Implementar como `LlmAgent` con Gemini Flash-Lite.
- La instruccion debe pedir al modelo que evalue si cada afirmacion de la respuesta esta respaldada por los chunks fuente.
- Devolver un resultado binario con lista de afirmaciones sin respaldo si las hay.

**Endpoint principal de conversacion**:
- Implementar `POST /v1/agent/chat` que inicializa la sesion si no existe y pasa el mensaje a Nexus.
- Soporte para streaming SSE de la respuesta.
- El endpoint de busqueda directa (`/v1/query`) se mantiene como alternativa sin agentes para casos donde se quiere control preciso.

**Pruebas**:
- Conversacion que requiere ingesta seguida de busqueda (Nexus debe delegar a Forge y luego a Atlas).
- Conversacion con pregunta ambigua donde Nexus debe pedir clarificacion.
- Verificar que Sentinel detecta una afirmacion que no esta en los chunks fuente.

### Criterio de exito

Una conversacion compleja que incluye ingesta de un documento nuevo y consulta sobre su contenido se maneja correctamente sin intervencion manual. Nexus delega a Forge y luego a Atlas de forma autonoma. Sentinel detecta al menos 1 de cada 3 alucinaciones en un conjunto de prueba.

---

## 9. Objetivo 6: Resiliencia y Modo Degradado

### Que se construye

El sistema aprende a sobrevivir a fallos parciales. Circuit breakers en todas las llamadas externas, reintentos inteligentes, backpressure en la cola, fallback a Docling cuando DeepSeek-OCR falla, fallback a solo BM25 cuando ChromaDB no responde, y modo degradado automatico bajo carga alta.

### Tareas especificas

**Circuit breakers**:
- Instalar `pybreaker` y crear instancias de `CircuitBreaker` para: DeepSeek-OCR, Gemini (embeddings), Gemini (vision), DeepSeek (generacion), ChromaDB.
- Configurar `fail_max` y `reset_timeout` desde variables de entorno.
- Registrar el estado de cada circuit breaker como metrica Prometheus.

**Fallback de OCR**:
- Cuando el circuit breaker de DeepSeek-OCR se abre, activar `DoclingAdapter` automaticamente.
- Loguear el evento de fallback con nivel WARNING.
- La respuesta de estado del documento debe indicar `"ocr_engine": "docling_fallback"`.

**Fallback de busqueda**:
- Cuando ChromaDB no responde (health check falla), ejecutar solo BM25.
- La respuesta de busqueda debe incluir `"retrieval_mode": "lexical_only"`.

**Reclamacion de mensajes caidos en la cola**:
- Implementar el mecanismo de CLAIM en el worker: periodicamente, el worker busca mensajes en el stream que llevan mas de N segundos sin ser confirmados (el worker que los procesaba murio).
- Si un mensaje falla 3 veces consecutivas (contador guardado en metadatos del mensaje), moverlo a la cola `ingest:failed`.

**Backpressure en la cola**:
- El endpoint de ingesta verifica la longitud del stream antes de aceptar nuevas tareas.
- Si la longitud supera el 80% de `QUEUE_MAXLEN`, devolver `429 Too Many Requests` con `Retry-After`.

**Modo degradado automatico**:
- Implementar un monitor de carga que evalua: longitud de cola, CPU de workers, latencia promedio de OCR.
- Si supera umbrales configurables, activar el modo degradado: desactivar Sentinel, reducir top_k de reranking, omitir enriquecimiento de imagenes en nuevas ingestas.
- El modo degradado se indica al usuario via header `X-System-Mode: degraded`.

**Pruebas de caos**:
- Prueba: apagar ChromaDB mientras se procesa una busqueda. Verificar que la respuesta llega con resultados BM25.
- Prueba: matar un worker mientras procesa un documento. Verificar que otro worker retoma la tarea.
- Prueba: saturar la cola enviando 100 documentos consecutivos. Verificar que los 429 se emiten correctamente.

### Criterio de exito

El sistema sigue respondiendo (aunque sea en modo degradado) cuando ChromaDB se apaga. Los documentos no se pierden cuando un worker muere a mitad del procesamiento. La cola no acepta mas de `QUEUE_MAXLEN * 0.8` mensajes sin devolver 429.

---

## 10. Objetivo 7: Almacenamiento en Nube

### Que se construye

Los tres tipos de activos del sistema (archivos originales e imagenes, vectores, sesiones) migran de almacenamiento local a servicios de nube con alta disponibilidad. El sistema es ahora completamente stateless en los pods.

### Por que en este punto

El almacenamiento en nube requiere que el sistema este completamente funcional y probado en local antes de agregar la complejidad operativa de servicios externos de nube. Ademas, las decisiones de almacenamiento dependen del volumen real de datos, que solo se conoce despues de que el sistema haya procesado documentos reales.

### Decisiones de almacenamiento en nube

Ver la seccion 14 de este documento para el analisis detallado. En resumen:

| Activo | Servicio elegido | Razon principal |
|--------|-----------------|-----------------|
| Imagenes y documentos | Cloudflare R2 | Cero costo de egreso, compatible con API S3 |
| Vectores (produccion) | Vertex AI Vector Search | SLA garantizado, escala automatica |
| Estado y cola | Redis gestionado (Redis Cloud o Memorystore) | Elimina sobrecarga operativa |
| Sesiones historicas | MongoDB Atlas o Firestore | Escala automatica, sin gestion |

### Tareas especificas

**Adaptador R2**:
- Implementar `R2StorageAdapter` usando `boto3` (R2 es compatible con la API de S3).
- Conversion automatica a WebP antes del upload.
- Generar URLs publicas con dominio propio si se configura un custom domain en R2.
- Prueba de upload, download y eliminacion.

**Adaptador Vertex AI Vector Search**:
- Implementar `VertexAIVectorAdapter` usando el SDK de Google Cloud AI Platform.
- Migrar los vectores existentes de ChromaDB a Vertex AI (script de migracion).
- Verificar que las busquedas devuelven los mismos resultados (tolerancia: diferencia < 5% en precision@5).

**Redis gestionado**:
- Actualizar `REDIS_DSN` para apuntar al servicio gestionado.
- Verificar que la autenticacion funciona (Redis Cloud usa autenticacion por password o ACL).
- Prueba de failover: el servicio gestionado debe recuperarse sin perdida de datos.

**Seleccion del backend via variables de entorno**:
- `STORAGE_BACKEND=r2`: activa R2 para archivos.
- `VECTOR_STORE_BACKEND=vertex_ai`: activa Vertex AI para vectores.
- El sistema debe poder cambiar entre local y nube sin cambiar codigo.

### Criterio de exito

El sistema funciona completamente usando los servicios de nube. Apagar el pod de la API y levantarlo de nuevo no pierde ningun estado. Un documento ingestado con el pod A puede ser consultado desde el pod B.

---

## 11. Objetivo 8: Despliegue en Kubernetes

### Que se construye

El sistema se despliega en Kubernetes con tres roles separados (API, Worker, Agent), escalado automatico basado en carga, health checks, TLS y ConfigMaps para configuracion.

### Tareas especificas

**Manifiestos base**:
- Crear `deployment-api.yaml`, `deployment-worker.yaml`, `deployment-agent.yaml`.
- Configurar resource requests y limits para cada rol.
- Configurar liveness y readiness probes.

**ConfigMaps y Secrets**:
- Variables no secretas en ConfigMap.
- Variables secretas (API keys) en Secrets, idealmente referenciados desde un sistema de gestion de secretos (Google Secret Manager o Vault).

**HPA para el rol API**:
- Escalar entre 2 y 10 replicas basado en CPU > 70% durante 2 minutos.

**KEDA para workers**:
- Instalar KEDA en el cluster.
- Configurar `ScaledObject` para el deployment de workers basado en la longitud del stream de Redis.
- Escalar entre 1 y 20 workers.

**Ingress con TLS**:
- Configurar `cert-manager` para emision automatica de certificados Let's Encrypt.
- Configurar Nginx Ingress con el dominio de produccion.

**Overlays de Kustomize**:
- Crear overlays para `development`, `staging` y `production` con las diferencias de configuracion entre entornos.

**Pipeline de CI/CD**:
- GitHub Actions que en cada push a `main`: ejecuta pruebas, construye la imagen Docker, la publica en el registry y aplica los manifiestos en el cluster de staging.
- Deploy a produccion: manual o con aprobacion.

### Criterio de exito

El sistema corre en Kubernetes con al menos 2 replicas de API y 1 worker. Eliminar una replica de API no interrumpe el servicio. Enviar 50 documentos a la vez hace que KEDA escale los workers automaticamente. Los certificados TLS son validos y auto-renovados.

---

## 12. Objetivo 9: Primera Vertical de Negocio

### Que se construye

La primera aplicacion real construida sobre el motor Nexa. Puede ser la plataforma de analisis documental (cualquier usuario puede subir documentos y conversar con ellos) o el motor de ventas conversacional (agente entrenado sobre un catalogo de productos).

La eleccion de la vertical en este punto depende de la oportunidad de mercado identificada durante los objetivos anteriores.

### Plataforma de analisis documental

**Frontend**:
- Interfaz web simple: subida de documentos, indicador de progreso, interfaz de chat.
- Tecnologia: Next.js o cualquier framework moderno que consuma la API REST de Nexa.
- Autenticacion de usuarios: Clerk, Auth0 o similar.

**Multitenancy**:
- Los documentos de cada usuario son privados: el `user_id` se agrega como filtro obligatorio en todas las busquedas.
- Planes de uso: numero maximo de documentos por usuario, numero maximo de consultas por mes.

**Motor de ventas conversacional**:

- El administrador del negocio carga el catalogo de productos como documentos estructurados.
- El agente Nexus se configura con una instruccion especializada en ventas: ofrecer productos relevantes, responder preguntas sobre disponibilidad y precio, cerrar la venta con un llamado a la accion.
- La interfaz del cliente es un widget de chat embebible en cualquier sitio web.

### Criterio de exito

Al menos un usuario externo (no el autor del sistema) puede completar el flujo completo de forma autonoma: subir un documento, hacer preguntas y obtener respuestas correctas. O: al menos un negocio puede conectar su catalogo y un cliente puede interactuar con el agente de ventas.

---

## 13. Objetivo 10: Escalado y Microservicios

### Que se construye

Cuando el volumen de uso justifica la complejidad operativa de los microservicios, se extraen los modulos mas costosos computacionalmente como servicios independientes. El orden de extraccion y los criterios para decidir cuando extraer estan definidos en INFRASTRUCTURE.md (seccion 13).

Este objetivo no tiene fecha de inicio determinada: comienza cuando las metricas de produccion muestran que un modulo especifico es el cuello de botella del sistema y que escalarlo de forma independiente produciria un beneficio significativo.

---

## 14. Decisiones de Almacenamiento en Detalle

### Imagenes y documentos originales

**Opcion local**: Sistema de archivos del servidor, montado como volumen persistente. Las imagenes se convierten a WebP antes de guardarlas. Funciona perfectamente para entornos de un solo servidor o cuando los pods comparten un volumen de red (NFS, GlusterFS).

**Opcion en nube: Cloudflare R2**

Cloudflare R2 es un servicio de almacenamiento de objetos compatible con la API de S3 de Amazon pero con una diferencia critica: no cobra por egreso de datos (la descarga de archivos es gratuita). Esto lo convierte en la opcion mas economica para un sistema que sirve imagenes frecuentemente.

```
Estructura de costos de R2 (abril 2026):
- Almacenamiento: $0.015 USD por GB por mes
- Operaciones PUT/COPY/LIST (clase A): $4.50 por millon de operaciones
- Operaciones GET/HEAD (clase B): $0.36 por millon de operaciones
- Egreso de datos: $0.00 (GRATIS)

Ejemplo para 10,000 documentos con promedio de 5 imagenes de 500KB (WebP):
- Almacenamiento: 10,000 * 5 * 0.0005 GB = 25 GB -> $0.375 / mes
- Uploads (PUT): 50,000 operaciones -> $0.225
- Downloads (GET, estimando 100 consultas por imagen): 5,000,000 operaciones -> $1.80
Total estimado: ~$2.40 USD / mes para 10,000 documentos con uso intensivo
```

Las imagenes se almacenan con nombres deterministas basados en el `chunk_id`, lo que permite reconstruir las URLs sin necesitar una base de datos adicional: `https://storage.nexa.com/{document_id}/{chunk_id}.webp`.

El uso de WebP reduce el tamano promedio de las imagenes entre un 25% y un 35% respecto a JPEG de calidad equivalente, con impacto directo en el costo de almacenamiento y en la velocidad de carga en el frontend.

**Cuando usar local**: Entorno de desarrollo, on-premise con requisito de privacidad de datos (los documentos no pueden salir del servidor), o volumen muy pequeno donde el costo de nube no se justifica.

**Cuando usar R2**: Produccion con acceso desde internet, cuando los pods no comparten un volumen de red, o cuando se quiere eliminar cualquier estado local en los pods.

### Vectores

**Opcion local: ChromaDB**

ChromaDB en modo persistente (con volumen de disco) es la opcion correcta para desarrollo y para produccion con menos de 10 millones de vectores. Es open-source, no tiene costo de uso y se opera como un contenedor Docker simple.

```
ChromaDB en Kubernetes:
- StatefulSet con un solo pod (no escala horizontalmente en modo open-source)
- PersistentVolumeClaim de 100GB (suficiente para ~50M vectores de 3072 dimensiones en float32)
- Backup diario mediante snapshot del volumen
```

La limitacion de ChromaDB es que no escala horizontalmente: un solo pod atiende todas las consultas. Para volumenes altos, esto puede convertirse en un cuello de botella.

**Opcion en nube: Vertex AI Vector Search**

Vertex AI Vector Search (anteriormente Matching Engine) es el servicio gestionado de Google para busqueda de vectores a escala. Escala automaticamente, tiene SLA del 99.9% y se integra con el ecosistema de Google que ya usa Nexa.

```
Estructura de costos de Vertex AI Vector Search (estimacion, verificar precios actuales):
- Almacenamiento de vectores: ~$0.10 USD por GB por hora (varia por configuracion)
- Un vector de 3072 dimensiones en float32 ocupa 12,288 bytes = ~12KB
- 1 millon de vectores = ~12 GB = ~$1.20 USD / hora = ~$864 USD / mes
- Las consultas tienen un costo adicional por millon de consultas

Este costo puede reducirse significativamente usando:
- Quantizacion de vectores a float16 (mitad del almacenamiento, perdida menor del 1% en precision)
- Archiving de vectores de documentos inactivos (documentos no consultados en mas de 90 dias)
```

**Recomendacion**: Comenzar con ChromaDB local. Migrar a Vertex AI Vector Search cuando el volumen de vectores supere los 5 millones o cuando ChromaDB muestre latencias superiores a 200ms en las busquedas. La migracion es transparente gracias al puerto `IVectorStore`.

### Estado, cola y sesiones

**Redis para estado y cola**: Redis debe ser el primer servicio en migrar a una version gestionada en produccion, porque es el componente mas critico del sistema. Si Redis cae, la API no puede procesar ingesta ni busquedas.

- Opcion Google Cloud: Memorystore for Redis (gestionado por Google, SLA 99.9%).
- Opcion independiente: Redis Cloud (disponible en cualquier proveedor de nube).
- Configuracion minima para produccion: instancia con alta disponibilidad (replica automatica en caso de fallo).

**MongoDB para sesiones historicas**: La persistencia historica de sesiones puede comenzar en MongoDB Atlas (plan gratuito hasta 512MB) y escalar segun necesidad. Tambien puede reemplazarse por Firestore si el equipo prefiere el ecosistema de Google.

---

## 15. Criterios para Actualizar el Roadmap

El roadmap debe actualizarse cuando:

**Aparece una tecnologia que cambia la ecuacion de costo o calidad**: Si un nuevo modelo de OCR ofrece la misma calidad que DeepSeek-OCR 2 a la mitad del costo, se evalua para sustituirlo. La evaluacion debe incluir: prueba con el mismo conjunto de documentos de referencia, medicion de precision, medicion de costo real y comparacion de latencia. Si supera en los tres criterios, se crea un ADR y se actualiza el objetivo correspondiente.

**Un objetivo tarda el doble de lo esperado**: Si un objetivo se extiende mas de lo razonable, se revisa si hay dependencias ocultas, si la complejidad fue subestimada o si el criterio de exito es demasiado ambicioso. Se puede dividir el objetivo en dos o ajustar el criterio de exito sin alterar los objetivos posteriores.

**El mercado indica una vertical diferente a la planificada**: Si durante los objetivos 1 al 8 se identifica una oportunidad de negocio mas urgente que la planificada en el Objetivo 9, el roadmap puede reordenarse. El motor (objetivos 1 al 8) es generico y sirve cualquier vertical.

**Una dependencia externa se vuelve inaceptable**: Si Novita AI cambia sus precios de forma drastica, si Gemini cambia sus condiciones de uso, o si cualquier proveedor externo presenta problemas de disponibilidad recurrentes, el objetivo correspondiente se prioriza para buscar alternativas y el ADR se actualiza.

**Cada actualizacion del roadmap requiere**: Un ADR que documente el cambio, la razon y el impacto en los objetivos siguientes. Sin ADR, el cambio no se aplica.

---

**Ever Mamani Vicente**  
evermamanivicente@gmail.com  
Abril 2026