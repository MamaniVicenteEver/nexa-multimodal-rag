# ADR-003: Finalización de la Fase 1, Arquitectura Multi-Tenant y Observabilidad Total

**Estado:** Aprobado e Implementado
**Periodo de Desarrollo:** 06/04/2026 al 17/04/2026 (11 días de ciclo de desarrollo)

## 1. Contexto y Visión General
Hemos completado oficialmente el **Objetivo 1 (Motor Mínimo Funcional)** y hemos sentado las bases para el **Objetivo 2 (Multimodalidad)**. En tan solo 11 días de desarrollo activo, el sistema ha pasado de ser un diseño teórico a un motor funcional capaz de ingerir documentos complejos (PDFs, TXTs), enrutarlos de manera inteligente para optimizar costos, indexarlos semánticamente y responder preguntas con alta precisión utilizando el modelo DeepSeek V3.2.

Para que este motor sea viable a nivel empresarial (Enterprise-ready), identificamos que un almacén de vectores monolítico generaría alucinaciones (mezclando información de distintos proyectos). Por ello, evolucionamos hacia una arquitectura **Multi-Tenant** estricta, complementada con un sistema de observabilidad forense.

## 2. Arquitectura de Datos: Patrón CQRS y Persistencia Políglota
Para separar las responsabilidades transaccionales (estado) de las analíticas (búsqueda semántica), implementamos persistencia políglota utilizando dos motores de bases de datos que trabajan en conjunto:

### A. PostgreSQL (Estado Relacional y Metadatos)
Actúa como la fuente de verdad del sistema transaccional. Almacena las métricas, la jerarquía de los datos y, lo más importante, gestiona la **Máquina de Estados** de los procesos asíncronos.
* **Tabla `collections`:** Representa los "proyectos" o bases de conocimiento aisladas. Almacena: `id`, `name`, `description`, métricas agregadas (`document_count`, `total_chunks`) y fechas de creación.
* **Tabla `documents`:** Representa los archivos físicos individuales. Almacena: `id`, `collection_id` (llave foránea lógica), `original_filename`, `mime_type`, recuento de fragmentos (`chunks_count`) y el ciclo de vida del archivo.
    * *Máquina de Estados:* Transita rigurosamente por `pending` -> `processing` -> `ready` (éxito) o `failed` (error).

### B. ChromaDB (Motor Vectorial Aislado)
* Los vectores ya no se vierten en una "piscina única". 
* **Creación Dinámica:** Cada vez que PostgreSQL registra una nueva colección, ChromaDB instancia un espacio vectorial (Collection) completamente aislado bajo el mismo `collection_id`.
* **Cero Alucinaciones:** Cuando el usuario realiza una consulta, el sistema fuerza a ChromaDB a buscar *exclusivamente* en los vectores de ese `collection_id`.

## 3. Observabilidad, Telemetría y Manejo de Errores
Tomamos la decisión arquitectónica de **no almacenar stack traces (trazas de error técnico) en la base de datos PostgreSQL** para evitar deuda técnica y sobrecarga de almacenamiento. En su lugar, implementamos un sistema dual:

### A. Rotación de Logs (Telemetría en Archivos)
Desplegamos manejadores rotativos (`TimedRotatingFileHandler`) estructurados en formato JSON puro, preparados para ser consumidos por herramientas forenses futuras (ej. Grafana, Loki o ELK).
* **`logs/app.log`:** Captura el flujo operativo normal (INFO/DEBUG). Se genera un archivo nuevo diariamente y los archivos históricos **se eliminan automáticamente tras 7 días** para liberar espacio.
* **`logs/error.log`:** Captura exclusivamente excepciones críticas y stack traces (ERROR/CRITICAL). Almacena los `doc_id` y `collection_id` para trazabilidad forense. Se rota diariamente y **se elimina automáticamente tras 30 días**.

### B. Resiliencia de la API (Global Exception Handler)
Para proteger la experiencia del cliente y la seguridad del servidor, FastAPI intercepta cualquier excepción (ya sea validación de Pydantic, errores de dominio o caídas no controladas) y devuelve una estructura JSON estandarizada y predecible. El cliente jamás recibe un error de servidor crudo.
Ejemplo del contrato de error: `{"error": true, "codigo": "SYSTEM_FAILURE", "message": "..."}`.

## 4. Diseño Hexagonal: Puertos y Adaptadores Activos
El núcleo de negocio está totalmente desacoplado de las dependencias externas. Si un proveedor cambia sus precios o cae, el motor no sufre, solo se cambia el adaptador.

| Puerto (Interfaz) | Adaptador Activo | Responsabilidad |
| :--- | :--- | :--- |
| `IOCRProvider` | `DeepSeekOCRAdapter` | Extracción visual multimodal profunda (Novita AI). |
| `IEmbeddingProvider` | `GeminiEmbeddingAdapter` | Vectorización de fragmentos (Google GenAI). |
| `ILLMClient` | `DeepSeekLLMAdapter` | Generación y síntesis final de respuestas. |
| `IVectorStore` | `ChromaDBAdapter` | Base de datos vectorial persistente local. |
| `IDatabaseRepository`| `PostgresRepositoryAdapter` | Motor relacional para multi-tenancy y estados. |
| `IFileStorage` | `LocalStorageAdapter` | Persistencia física de archivos en el disco duro. |

## 5. Enrutamiento Híbrido: Optimización Quirúrgica de Costos
Implementamos el `HybridDocumentProcessor`. En lugar de enviar ciegamente documentos de cientos de páginas al OCR visual (lo que saturaría la red y dispararía los costos de tokens API), el sistema evalúa cada página localmente usando `PyMuPDF`.
* **Ruta Local (Costo $0):** Si la página es texto plano, se extrae en CPU local en milisegundos.
* **Ruta Externa (OCR Visual):** Solo si la página contiene imágenes incrustadas, dibujos vectoriales (tablas/gráficos) o carece de texto seleccionable (escaneos), se convierte a PNG y se delega a DeepSeek-OCR.

## 6. Contratos de API (Endpoints Disponibles)
El sistema expone 4 rutas críticas de forma asíncrona:

1.  **`GET /health`:** Monitorización del nodo y su rol.
2.  **`GET /v1/collections/`:** Lista el directorio de bases de conocimiento con paginación (`skip`, `limit`) y filtros temporales (`start_date`, `end_date`).
3.  **`POST /v1/query/`:** Ejecuta el pipeline RAG requiriendo estrictamente un `collection_id` y el `question`.
4.  **`POST /v1/ingest/`:** Endpoint `multipart/form-data` para subida de documentos. 
    * **Comportamiento Asíncrono:** Retorna inmediatamente un 200 OK con el estado `pending`, delegando la extracción híbrida, el chunking, la vectorización y la actualización de PostgreSQL a un hilo en segundo plano (Background Task).
