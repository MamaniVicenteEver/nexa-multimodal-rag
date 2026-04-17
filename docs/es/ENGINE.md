# ENGINE.md
# Nexa Multimodal RAG — Motor de Inteligencia Documental (v2.0)

**Autor:** Ever Mamani Vicente  
**Contacto:** evermamanivicente@gmail.com  
**Fecha:** Abril 2026

> Este documento describe el corazon funcional del sistema Nexa: como procesa documentos, como recupera informacion, como genera respuestas y como los agentes coordinan todo el trabajo. Cada decision de diseno incluye la razon que la sustenta. Para la arquitectura de infraestructura, despliegue y escalabilidad, consultar INFRASTRUCTURE.md.

---

## Tabla de Contenidos

1. [Proposito y Objetivos del Motor](#1-proposito-y-objetivos-del-motor)
2. [Entidades del Dominio](#2-entidades-del-dominio)
3. [Pipeline de Ingesta: Flujo Completo](#3-pipeline-de-ingesta-flujo-completo)
   - 3.1 [Extraccion estructural con DeepSeek-OCR 2](#31-extraccion-estructural-con-deepseek-ocr-2)
   - 3.2 [Limpieza y normalizacion](#32-limpieza-y-normalizacion)
   - 3.3 [Chunking semantico](#33-chunking-semantico)
   - 3.4 [Enriquecimiento de imagenes](#34-enriquecimiento-de-imagenes)
   - 3.5 [Vectorizacion](#35-vectorizacion)
   - 3.6 [Almacenamiento dual](#36-almacenamiento-dual)
4. [Pipeline de Consulta: Flujo Completo](#4-pipeline-de-consulta-flujo-completo)
   - 4.1 [Self-querying estructurado](#41-self-querying-estructurado)
   - 4.2 [Recuperacion hibrida (Dual Retrieval)](#42-recuperacion-hibrida-dual-retrieval)
   - 4.3 [Re-ranking con cross-encoder](#43-re-ranking-con-cross-encoder)
   - 4.4 [Ensamblado del prompt y generacion](#44-ensamblado-del-prompt-y-generacion)
5. [Memoria de Conversacion y Sesiones](#5-memoria-de-conversacion-y-sesiones)
6. [El Sistema de Agentes](#6-el-sistema-de-agentes)
   - 6.1 [Nexus: El Agente Supervisor](#61-nexus-el-agente-supervisor)
   - 6.2 [Atlas: El Agente de Recuperacion](#62-atlas-el-agente-de-recuperacion)
   - 6.3 [Forge: El Agente de Ingesta](#63-forge-el-agente-de-ingesta)
   - 6.4 [Sentinel: El Agente Validador](#64-sentinel-el-agente-validador)
   - 6.5 [Coordinacion entre agentes](#65-coordinacion-entre-agentes)
7. [Ejemplos JSON de Extremo a Extremo](#7-ejemplos-json-de-extremo-a-extremo)
8. [Estrategias de Optimizacion Interna](#8-estrategias-de-optimizacion-interna)
9. [Analisis de Decisiones Tecnicas](#9-analisis-de-decisiones-tecnicas)

---

## 1. Proposito y Objetivos del Motor

El motor RAG de Nexa no es simplemente una implementacion de recuperacion aumentada por generacion. Es una plataforma de inteligencia documental disenada para resolver un problema de negocio especifico: permitir que cualquier persona o sistema interactue con documentos complejos en lenguaje natural, obteniendo respuestas precisas, trazables y economicamente viables a escala industrial.

### Objetivos de calidad

**Precision de recuperacion**: Que los fragmentos devueltos al modelo generador sean los mas relevantes posibles para la pregunta formulada. Esto se logra mediante la combinacion de busqueda vectorial (captura similitud semantica) y busqueda lexica (captura terminos exactos), seguida de re-ranking para refinar la precision.

**Respuestas trazables**: Cada respuesta generada incluye referencias a los fragmentos de origen, con numero de pagina y tipo de contenido (texto, imagen, tabla). El usuario puede verificar cualquier afirmacion del sistema en la fuente original.

**Memoria conversacional coherente**: El sistema recuerda el contexto de la conversacion y puede inferir referencias implicitas. Si el usuario dice "del mismo documento, dime las conclusiones", el sistema sabe a que documento se refiere sin que el usuario lo repita.

**Multimodalidad real**: Las imagenes, graficos y tablas no se ignoran. Se describen, se indexan y se recuperan con la misma precision que el texto. Una pregunta sobre un grafico de ventas encuentra la descripcion del grafico y la responde correctamente.

### Objetivos de costo

El motor esta optimizado para minimizar el costo por operacion sin sacrificar la calidad. Esto se logra mediante:

- Seleccion del modelo mas economico que tenga calidad suficiente para cada tarea especifica.
- Cache de embeddings para documentos identicos (mismo hash SHA-256).
- Fallbacks locales cuando los servicios externos tienen alta latencia o costo elevado.
- Dual retrieval que reduce el numero de tokens enviados al modelo generador al eliminar candidatos irrelevantes antes de la generacion.

### Objetivos de competitividad

El objetivo final es que un usuario no pueda distinguir la calidad de las respuestas de Nexa de las de sistemas similares ofrecidos por grandes corporaciones, pero a una fraccion del costo de infraestructura.

---

## 2. Entidades del Dominio

Las entidades son los objetos fundamentales del sistema. Representan conceptos del negocio con validacion y semantica propias.

### Document

Representa un archivo subido por el usuario. Registra todo el ciclo de vida del procesamiento.

```python
@dataclass
class Document:
    id: str                          # UUID v4 unico
    original_filename: str           # Nombre original del archivo
    original_url: Optional[str]      # URL de origen si se subio por enlace
    content_hash: Optional[str]      # SHA-256 del contenido binario (deduplicacion)
    status: DocumentStatus           # pending | processing | ready | failed
    pages: int                       # Numero de paginas detectadas por OCR
    chunks_count: int                # Chunks generados tras el procesamiento
    chunk_ids: List[str]             # Referencias a los chunks hijos
    error_message: Optional[str]     # Mensaje de error si status == failed
    instruction: Optional[str]       # Instruccion de contexto del usuario al ingestar
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]         # Tamano en bytes, tipo MIME, etc.
```

El campo `instruction` es uno de los elementos mas importantes del diseno. Permite al usuario informar al sistema sobre el contexto del documento antes de procesarlo: "Este documento es un contrato legal en ingles tecnico" o "Este PDF contiene tablas financieras en formato IFRS". Esta instruccion se pasa al OCR para mejorar la interpretacion y al modelo de vision para mejorar las descripciones de imagenes.

### Chunk

La unidad minima de informacion que se indexa y recupera. Un documento de 50 paginas puede generar entre 100 y 500 chunks segun la densidad de contenido.

```python
@dataclass
class Chunk:
    id: str                          # UUID v4
    document_id: str                 # Referencia al documento padre
    type: ChunkType                  # text | image | table | formula
    content: str                     # Texto del fragmento (o descripcion si es imagen)
    embedding: Optional[List[float]] # Vector de 3072 dimensiones (Gemini Embedding 2)
    metadata: Dict[str, Any]         # page_num, section, bbox, token_count, etc.
    image_url: Optional[str]         # URL del archivo de imagen (solo chunks de imagen)
    context_before: Optional[str]    # Parrafo anterior a la imagen (preserva contexto)
    context_after: Optional[str]     # Parrafo posterior a la imagen
    created_at: datetime
```

La separacion por tipo (`ChunkType`) permite aplicar estrategias de recuperacion y validacion diferentes para cada tipo. Las tablas, por ejemplo, se indexan con un prompt de busqueda diferente que prioriza la busqueda de valores numericos exactos.

### Session

Representa una conversacion completa con su historial y contexto activo.

```python
@dataclass
class Session:
    id: str                          # session_id proporcionado o generado
    user_id: str                     # Identificador del usuario
    created_at: datetime
    updated_at: datetime
    history: List[ConversationTurn]  # Turnos de la conversacion
    active_document_id: Optional[str]  # Documento "en foco" de la sesion
    active_filters: Dict[str, Any]   # Filtros activos de busqueda
    language: str                    # Idioma preferido del usuario
    metadata: Dict[str, Any]

@dataclass
class ConversationTurn:
    role: str                        # "user" o "assistant"
    content: str
    timestamp: datetime
    attachments: List[str]           # IDs de documentos mencionados en este turno
    source_chunks: List[str]         # IDs de chunks usados para generar la respuesta
```

### Query

Registra cada interaccion de busqueda para auditoria y mejora continua del sistema.

```python
@dataclass
class Query:
    id: str
    session_id: str
    original_text: str               # Pregunta original del usuario
    parsed_intent: ParsedIntent      # Intencion estructurada extraida por self-querying
    retrieval_chunks: List[str]      # IDs de chunks recuperados antes del reranking
    reranked_chunks: List[str]       # IDs de chunks tras el reranking (top K)
    answer: str                      # Respuesta generada
    validation_passed: bool          # Si el validador aprobo la respuesta
    latency_ms: int                  # Latencia total de la operacion
    cost_usd: float                  # Costo estimado de la operacion
    timestamp: datetime

@dataclass
class ParsedIntent:
    semantic_query: str              # Reescritura para busqueda vectorial
    keywords: List[str]              # Terminos para busqueda lexica
    filters: Dict[str, Any]         # Filtros de metadata (document_id, fecha, etc.)
    language: str                    # Idioma detectado
```

---

## 3. Pipeline de Ingesta: Flujo Completo

La ingesta es el proceso que transforma un archivo binario (PDF, imagen, Word) en chunks indexados y listos para ser recuperados. Es un proceso completamente asincrono: el usuario recibe un `document_id` en menos de 100ms y el procesamiento ocurre en segundo plano.

### 3.1 Extraccion estructural con DeepSeek-OCR 2

El primer paso del pipeline es convertir el documento en Markdown estructurado. DeepSeek-OCR 2, accedido a traves de la API de Novita AI, analiza la pagina como imagen y genera una representacion semanticamente fiel que preserva el layout, las tablas, el orden de lectura en columnas multiples y las referencias a imagenes.

El costo de DeepSeek-OCR 2 es de $0.03 por millon de tokens de entrada y salida, frente a los $2.00 de Mistral OCR 3 para el mismo volumen. Esto representa una reduccion de costo del 98.5% manteniendo una precision comparable (91% en el benchmark OmniDocBench vs 93% de Mistral). Para un sistema que procesa miles de paginas al dia, esta diferencia es determinante.

```python
# Llamada al adaptador de OCR
async def extract_page(self, page_image: bytes, instruction: str) -> str:
    img_b64 = base64.b64encode(page_image).decode()
    prompt = "<|grounding|>Convert this document page to Markdown."
    if instruction:
        prompt += f" Context provided by user: {instruction}"

    response = await self.client.chat.completions.create(
        model="deepseek/deepseek-ocr-2",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": f"data:image/png;base64,{img_b64}"},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    return response.choices[0].message.content
```

El resultado es Markdown estructurado por pagina. Las imagenes aparecen como referencias (`![descripcion](imagen_001.png)`) y las tablas como Markdown de tabla estandar. DeepSeek-OCR 2 tambien devuelve las imagenes extraidas en Base64 o como archivos temporales, segun la configuracion.

Para documentos de texto plano (TXT, Markdown), el adaptador de Docling se usa directamente sin consumir tokens de OCR.

### 3.2 Limpieza y normalizacion

El Markdown crudo del OCR contiene artefactos comunes: numeros de pagina aislados, encabezados y pies de pagina repetitivos, saltos de linea dentro de palabras causados por el layout original, caracteres especiales mal codificados.

La limpieza se realiza con reglas deterministicas (expresiones regulares) y transformaciones logicas simples. No se usa un LLM para esta fase porque es una tarea deterministicas donde el LLM no aportaria calidad adicional pero si latencia y costo.

```python
import re

def clean_markdown(raw_text: str) -> str:
    # Eliminar numeros de pagina aislados (ej: "- 42 -" o "42\n" al inicio de parrafo)
    text = re.sub(r'^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$', '', raw_text, flags=re.MULTILINE)

    # Unir palabras partidas por guion en salto de linea
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)

    # Eliminar lineas de solo espacios o guiones (separadores de columna)
    text = re.sub(r'^\s*[|\-+]{3,}\s*$', '', text, flags=re.MULTILINE)

    # Normalizar multiples lineas en blanco a maximo dos
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Normalizar fechas textuales a ISO (opcional, dependiendo del dominio)
    # "Enero 2025" -> "2025-01-01"
    # Esta transformacion se activa segun el tipo de documento
    return text.strip()
```

### 3.3 Chunking semantico

El Markdown limpio se divide en chunks. La estrategia de chunking afecta directamente la precision de la recuperacion: chunks demasiado pequenos pierden contexto, chunks demasiado grandes diluyen la similitud semantica en el vector y generan mayor costo en el modelo generador.

Se usa `RecursiveCharacterTextSplitter` con jerarquia de separadores: primero intenta dividir por secciones (`##`), luego por parrafos (`\n\n`), luego por oraciones (`. `), y finalmente por caracteres. Esto garantiza que cada chunk sea la unidad semantica mas grande posible dentro del limite de tokens configurado (1000 tokens por defecto).

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

def chunk_document(text: str, max_tokens: int = 1000) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(
        separators=["## ", "\n\n", "\n", ". ", " ", ""],
        chunk_size=max_tokens,
        chunk_overlap=100,           # Solapamiento para preservar contexto en fronteras
        length_function=count_tokens  # Usar tokenizador real, no longitud de caracteres
    )
    return splitter.split_text(text)
```

El solapamiento de 100 tokens entre chunks consecutivos asegura que una idea que cruza la frontera entre dos chunks sea recuperable desde cualquiera de los dos.

Las tablas reciben tratamiento especial: se detectan como bloques de Markdown de tabla (`| col | col |`) y se chunkizan como unidades completas, nunca partidas a la mitad, aunque excedan el limite de tokens. Una tabla incompleta no tiene valor semantico.

### 3.4 Enriquecimiento de imagenes

Este es uno de los pasos mas diferenciadores del sistema. La mayoria de los sistemas RAG ignoran las imagenes o las descartan. Nexa las procesa y las hace completamente recuperables mediante busqueda semantica.

El proceso es el siguiente:

**Paso 1**: Detectar referencias a imagenes en el Markdown (`![...](ruta)`).

**Paso 2**: Extraer el contexto circundante: el parrafo anterior (hasta 500 caracteres) y el parrafo posterior (hasta 500 caracteres) a la referencia de imagen.

**Paso 3**: Construir un prompt multimodal para Gemini 3.1 Flash-Lite que incluye la imagen en Base64 y el contexto textual.

```
Analiza esta imagen en el contexto del documento.

Texto antes de la imagen:
{context_before}

Texto despues de la imagen:
{context_after}

Describe la imagen de forma autocontenida, incluyendo:
- Que tipo de contenido visual es (grafico, foto, diagrama, tabla visual, ilustracion)
- Los datos o conceptos principales que muestra
- Numeros, tendencias o relaciones relevantes si los hay
- Como se relaciona con el texto que la rodea

La descripcion debe tener entre 50 y 200 palabras y debe ser comprensible sin ver la imagen.
```

**Paso 4**: La descripcion generada se convierte en el campo `content` del chunk de imagen. La imagen fisica se almacena en el sistema de archivos (local o R2). El chunk de imagen tiene exactamente la misma estructura que un chunk de texto y se indexa de la misma manera.

Gemini 3.1 Flash-Lite se eligio para esta tarea por su costo extremadamente bajo ($0.25 por millon de tokens de entrada incluyendo imagenes), su capacidad multimodal nativa y su velocidad suficiente para procesamiento asincrono. DeepSeek-OCR 2 no es adecuado para generar descripciones ricas porque esta optimizado para extraccion de texto, no para captioning.

```python
# Ejemplo de chunk de imagen enriquecido
{
    "id": "chunk_img_042",
    "document_id": "doc_2026_001",
    "type": "image",
    "content": "Grafico de barras verticales que muestra la evolucion de ventas mensuales durante el Q3 2025. Julio registra 120,000 USD, agosto 135,000 USD y septiembre 150,000 USD, con una tendencia ascendente del 25% entre el primer y el ultimo mes del trimestre. El grafico complementa la tabla de ingresos de la pagina anterior e ilustra el impacto positivo de la campana de marketing lanzada en agosto.",
    "image_url": "/storage/images/doc_2026_001_img_042.webp",
    "metadata": {
        "page": 2,
        "bbox": [100, 200, 700, 450],
        "context_before": "La siguiente grafica resume el desempeno comercial del trimestre:",
        "context_after": "Este crecimiento sostenido supera las proyecciones del plan anual en un 8%."
    },
    "embedding": [...]
}
```

### 3.5 Vectorizacion

Cada chunk (texto o imagen-como-texto) se convierte en un vector de 3072 dimensiones usando `gemini-embedding-2-preview`. El vector captura el significado semantico del contenido de forma que fragmentos con conceptos similares queden cerca en el espacio vectorial, independientemente de las palabras exactas usadas.

La cache de embeddings asegura que si dos documentos tienen el mismo contenido (mismo hash SHA-256), los vectores no se regeneran: se copian desde el documento anterior. Esto es relevante para sistemas donde se ingestan versiones de documentos con pequenas diferencias.

Los embeddings de imagenes se generan sobre la descripcion textual, no sobre la imagen directamente. Esto asegura compatibilidad con el indice vectorial existente y consistencia en la busqueda.

### 3.6 Almacenamiento dual

Cada chunk se almacena en dos indices complementarios:

**ChromaDB (o Vertex AI Vector Search en produccion)**: Almacena el vector de embeddings junto con los metadatos del chunk. Permite busqueda por similitud semantica.

**Indice BM25 (rank-bm25)**: Almacena el texto tokenizado del chunk. Permite busqueda por presencia exacta de terminos. Un fragmento que mencione "error 404" o "ISO 27001" sera encontrado por BM25 aunque ninguna busqueda vectorial lo detecte como semanticamente relevante.

El indice BM25 se mantiene en memoria (o se serializa a disco/Redis para persistencia). Se reconstruye desde ChromaDB si se reinicia el sistema.

---

## 4. Pipeline de Consulta: Flujo Completo

La consulta es el proceso que convierte una pregunta en lenguaje natural en una respuesta precisa, trazable y en streaming. Opera en tiempo real con un timeout configurable (5 segundos por defecto antes de devolver respuesta parcial).

### 4.1 Self-querying estructurado

Antes de buscar, el sistema analiza la pregunta para extraer tres componentes utiles para la busqueda:

- La **intencion semantica**: una reescritura de la pregunta orientada a busqueda vectorial, mas descriptiva y sin ambiguedades.
- Las **palabras clave exactas**: terminos criticos que deben aparecer literalmente en los resultados.
- Los **filtros de metadata**: restricciones sobre los resultados (document_id especifico, rango de fechas, tipo de chunk, etc.).

Este analisis se realiza con Gemini 3.1 Flash-Lite, que es suficientemente capaz para esta tarea de extraccion estructurada y extremadamente economico.

```
Sistema: Eres un analizador de consultas para un sistema de busqueda documental.
Extrae los siguientes componentes de la pregunta del usuario en formato JSON:
- semantic_query: reescritura de la pregunta para busqueda semantica
- keywords: lista de terminos que deben aparecer exactamente en los resultados
- filters: objeto con restricciones de metadata (document_id, date_range, content_type)
- language: idioma detectado ("es", "en", etc.)

Responde SOLO con JSON valido, sin explicaciones.

Usuario: "Cuanto aumentaron las ventas en septiembre segun el informe de Q3?"
```

Respuesta esperada:

```json
{
    "semantic_query": "incremento porcentual de ventas en el mes de septiembre tercer trimestre",
    "keywords": ["ventas", "septiembre", "Q3", "aumento"],
    "filters": {
        "month": "septiembre",
        "period": "Q3"
    },
    "language": "es"
}
```

Si la sesion tiene un `active_document_id`, el sistema lo agrega automaticamente a los filtros antes de ejecutar la busqueda, sin necesidad de que el usuario lo mencione.

### 4.2 Recuperacion hibrida (Dual Retrieval)

Con la intencion estructurada, se ejecutan dos busquedas en paralelo:

**Busqueda vectorial**: El `semantic_query` se vectoriza con Gemini Embedding 2 y se consulta ChromaDB aplicando los filtros de metadata como clausulas WHERE. Devuelve los 20 chunks mas similares semanticamente.

**Busqueda lexica**: Los `keywords` se buscan en el indice BM25 con los mismos filtros. Devuelve los 20 chunks con mayor frecuencia de terminos relevantes.

**Fusion RRF**: Los dos rankings se combinan con Reciprocal Rank Fusion:

```
score_rrf(chunk) = sum(1 / (k + rank_en_lista)) para cada lista
```

Donde `k = 60` es una constante que suaviza la influencia de los primeros puestos. RRF no requiere entrenamiento, es robusto ante diferencias de escala entre los dos rankings y funciona bien en la practica sin ajuste de parametros.

El resultado es una lista unica de hasta 40 candidatos ordenados por relevancia combinada.

### 4.3 Re-ranking con cross-encoder

Los 40 candidatos de la fusion RRF pasan por un segundo nivel de clasificacion usando `BAAI/bge-reranker-v2-m3`.

La diferencia entre embeddings y cross-encoders es fundamental:

- Un **embedding** (bi-encoder) convierte la pregunta y el fragmento en vectores de forma independiente. La similitud se calcula como distancia entre vectores. Es rapido pero aproximado.
- Un **cross-encoder** recibe la pregunta y el fragmento juntos y calcula una puntuacion de relevancia evaluando la interaccion entre ambos textos. Es mucho mas preciso pero tambien mas lento.

La combinacion de ambos es la estrategia optima: los embeddings hacen una seleccion rapida de candidatos (de millones a 40), y el cross-encoder hace una seleccion precisa (de 40 a 5). El costo computacional del cross-encoder sobre 40 pares es aceptable.

BGE-reranker-v2-m3 es open-source, funciona en CPU (aunque mas lento) y tiene calidad cercana a modelos de pago como Cohere Rerank, que seria mas caro y dependiente de un proveedor externo.

### 4.4 Ensamblado del prompt y generacion

Los 5 chunks mejor clasificados por el cross-encoder, el historial de los ultimos 5 turnos de la sesion y la pregunta original se combinan en un prompt estructurado para DeepSeek-V3.2:

```
Eres un asistente especializado en analisis de documentos.
Responde la pregunta del usuario basandote EXCLUSIVAMENTE en los fragmentos proporcionados.
Si la informacion no esta en los fragmentos, indica que no puedes responderla con los datos disponibles.
Incluye al final una seccion de fuentes citando el numero de pagina y tipo de contenido de cada fragmento utilizado.

HISTORIAL DE CONVERSACION:
[Ultimos 5 turnos]

FRAGMENTOS RECUPERADOS:
[Chunk 1: Pagina 3, tipo texto]
Las ventas aumentaron un 15% en el tercer trimestre...

[Chunk 2: Pagina 5, tipo imagen]
Grafico de barras que muestra ventas mensuales: Julio $120k, Agosto $135k, Septiembre $150k...

PREGUNTA: Cuanto aumentaron las ventas en septiembre?
```

DeepSeek-V3.2 se eligio como generador final por su excelente relacion calidad-precio: $0.28 por millon de tokens de entrada (cache miss) y $0.42 por millon de salida, frente a $5.00 / $15.00 de GPT-4o y $2.00 / $12.00 de Gemini 3.1 Pro. En evaluaciones internas sobre tareas de sintesis documental, DeepSeek-V3.2 alcanza una calidad comparable al 94% de GPT-4o a menos del 10% del costo.

La respuesta se entrega en streaming SSE, lo que permite que el usuario comience a leer mientras el modelo termina de generar.

---

## 5. Memoria de Conversacion y Sesiones

El sistema de sesiones permite que el usuario mantenga una conversacion coherente a lo largo del tiempo, con referencias implicitas a documentos y contexto previo.

### Estado activo de sesion (Redis)

Cada sesion activa se almacena en Redis con un TTL configurable (24 horas por defecto). La clave de Redis es `session:{session_id}` y el valor es un JSON serializado con el estado completo de la sesion.

Redis se elige para estado activo porque opera en memoria, tiene latencia sub-milisegundo, gestiona expiracion automatica de sesiones (TTL) y es compartido entre todos los pods del cluster.

### Estado historico de sesion (MongoDB, opcional)

Para cumplimiento, auditoria o capacidades de fine-tuning futuras, las sesiones completadas pueden persistirse en MongoDB. Esta persistencia es opcional y no afecta el funcionamiento del sistema si MongoDB no esta disponible.

### Manejo de referencias implicitas

El agente supervisor (Nexus) gestiona las referencias implicitas usando el estado de la sesion:

```
Usuario: "Procesa este PDF" (adjunta informe_q3.pdf)
Sistema: Documento procesado. ID: doc_2026_001.
[El sistema guarda active_document_id = "doc_2026_001" en la sesion]

Usuario: "Del mismo documento, dime cuales son las conclusiones"
[Nexus lee active_document_id de la sesion y lo agrega como filtro]
[La busqueda se ejecuta solo sobre doc_2026_001]
Sistema: Las conclusiones del informe son...

Usuario: "Puedes comparar esto con el informe del Q2?" (adjunta informe_q2.pdf)
[Nexus detecta que el usuario adjunta un nuevo documento]
[Forge inicia la ingesta; active_document_id pasa a ser un array con ambos documentos]
[Atlas ejecuta la busqueda con filtro de document_id in [doc_2026_001, doc_2026_002]]
```

---

## 6. El Sistema de Agentes

El sistema de agentes de Nexa esta construido sobre Google ADK 2.0 y esta disenado siguiendo un modelo jerarquico: un agente supervisor coordina a tres agentes especializados, cada uno con herramientas y responsabilidades bien definidas.

Los agentes permiten manejar la ambiguedad del lenguaje natural que reglas deterministicas no pueden resolver. Tambien permiten encadenar operaciones complejas (ingestar un documento y luego compararlo con otro ya existente) de forma autonoma.

### 6.1 Nexus: El Agente Supervisor

Nexus es el punto de entrada de toda interaccion del usuario con el sistema. Recibe el mensaje del usuario, analiza el contexto de la sesion, decide que accion tomar y coordina a los demas agentes o responde directamente si la pregunta no requiere busqueda documental.

**Modelo**: Gemini 3.1 Pro. Se elige el modelo mas capaz del stack para el supervisor porque sus decisiones afectan a todas las demas operaciones. Una clasificacion incorrecta de la intencion del usuario resulta en una respuesta incorrecta, independientemente de la calidad del retrieval.

**Herramientas disponibles para Nexus**:

- `delegate_to_atlas(query, session_context)`: Delega la busqueda documental al agente Atlas.
- `delegate_to_forge(file_url, instruction, session_id)`: Delega la ingesta de un nuevo documento al agente Forge.
- `ask_clarification(question)`: Solicita informacion adicional al usuario cuando la intencion es ambigua.
- `answer_general(question)`: Responde directamente preguntas generales que no requieren busqueda en documentos.
- `update_session(active_document_id, filters)`: Actualiza el estado de la sesion activa.

**Logica de decision de Nexus**:

```python
supervisor_instruction = """
Eres Nexus, el coordinador inteligente del sistema Nexa.
Tu funcion es analizar cada mensaje del usuario y decidir la mejor accion.

Reglas de decision:
1. Si el usuario adjunta un archivo o proporciona una URL de documento, delega a Forge para la ingesta.
2. Si el usuario hace una pregunta sobre documentos (que incluya "en el documento", "segun el informe",
   referencias a datos especificos, etc.), delega a Atlas para la busqueda.
3. Si la pregunta es de conocimiento general (sin referencia a documentos), responde directamente.
4. Si la intencion es ambigua, usa ask_clarification para obtener mas contexto.
5. Si el usuario se refiere a "el mismo documento" o "el anterior", usa el active_document_id
   de la sesion como filtro en la delegacion a Atlas.
6. Si el usuario pide comparar documentos, delega a Atlas con multiples document_ids.

Estado actual de la sesion:
- active_document_id: {active_document_id}
- historial reciente: {conversation_history}
"""
```

### 6.2 Atlas: El Agente de Recuperacion

Atlas es el agente especializado en busqueda documental. Ejecuta el pipeline completo de recuperacion hibrida, incluyendo self-querying, dual retrieval, re-ranking y generacion de respuesta.

**Modelo**: DeepSeek-V3.2 para la generacion final. Las etapas intermedias (self-querying) usan Gemini 3.1 Flash-Lite.

**Herramientas disponibles para Atlas**:

- `search_vector_store(query_vector, filters, top_k)`: Consulta ChromaDB.
- `search_lexical_index(keywords, filters, top_k)`: Consulta el indice BM25.
- `rerank_candidates(query, candidates)`: Aplica el cross-encoder BGE sobre los candidatos.
- `generate_response(prompt, stream)`: Llama a DeepSeek-V3.2 con streaming.
- `get_chunk_details(chunk_ids)`: Recupera el contenido completo y metadatos de chunks especificos.

Atlas sigue siempre el mismo flujo: self-query -> dual retrieval -> fusion RRF -> reranking -> generacion. No toma decisiones sobre si buscar o no; eso es responsabilidad de Nexus.

### 6.3 Forge: El Agente de Ingesta

Forge gestiona el ciclo de vida completo de un documento: desde la recepcion hasta la confirmacion de indexacion. Opera principalmente coordinando el pipeline de ingesta asincrono.

**Herramientas disponibles para Forge**:

- `create_document_record(url, filename, instruction)`: Crea el registro de documento con estado PENDING.
- `enqueue_ingestion_task(document_id, file_bytes)`: Publica la tarea en la cola Redis Streams.
- `check_document_status(document_id)`: Consulta el estado actual del documento en Redis.
- `handle_duplicate(content_hash)`: Verifica si el documento ya existe por su hash SHA-256.

Forge no ejecuta el OCR ni el chunking directamente. Encola la tarea y el worker del modulo de ingesta ejecuta el procesamiento real. Forge puede, si el usuario lo solicita, hacer polling del estado y notificar cuando el documento esta listo.

### 6.4 Sentinel: El Agente Validador

Sentinel verifica que las respuestas generadas por Atlas esten fundamentadas en los fragmentos recuperados y no contengan alucinaciones.

**Modelo**: Gemini 3.1 Flash-Lite. La validacion es una tarea de clasificacion binaria (la respuesta esta fundamentada / no esta fundamentada), para la que un modelo economico es suficiente.

**Herramientas disponibles para Sentinel**:

- `check_faithfulness(answer, source_chunks)`: Verifica que cada afirmacion de la respuesta este respaldada por al menos un chunk fuente.
- `flag_unsupported_claims(answer, source_chunks)`: Identifica y marca las afirmaciones sin respaldo.

Sentinel opera despues de que Atlas genera la respuesta. Si detecta afirmaciones sin respaldo, la respuesta se regenera con un prompt mas restrictivo o se indica al usuario que ciertas partes no estan documentadas en los fragmentos disponibles.

Sentinel puede desactivarse en modo degradado (cuando la carga del sistema es alta) para priorizar la latencia. Esta desactivacion es automatica y se indica al usuario mediante un header en la respuesta (`X-Validation-Skipped: true`).

### 6.5 Coordinacion entre agentes

El flujo tipico de una conversacion ilustra como interactuan los cuatro agentes:

```
Usuario: "Aqui esta el informe anual de la empresa. Quiero saber como evolucionaron
          las ventas por region y comparar con el informe del ano anterior."

[Nexus analiza el mensaje]
[Nexus detecta: adjunto un nuevo documento]
[Nexus delega a Forge: ingestar el nuevo documento]

Forge: Documento encolado. ID: doc_2026_annual.
[Forge hace polling hasta que el documento esta en estado READY]
[Forge notifica a Nexus: documento listo]

[Nexus actualiza la sesion: active_document_ids = [doc_2026_annual, doc_2025_annual]]
[Nexus detecta: pregunta comparativa sobre documentos -> delega a Atlas]

Atlas ejecuta:
1. Self-query: "evolucion de ventas por region, comparacion interanual"
2. Dual retrieval con filtro document_id in [doc_2026_annual, doc_2025_annual]
3. Recupera chunks de ambos documentos: tablas de ventas, graficos, resumen ejecutivo
4. Reranking: selecciona los 5 mas relevantes
5. Genera respuesta comparativa con citas a ambos documentos

[Sentinel verifica que la comparacion cite datos reales de ambos documentos]

Sistema devuelve la respuesta en streaming con fuentes de ambos documentos.
```

---

## 7. Ejemplos JSON de Extremo a Extremo

### Ingesta de un documento

**Peticion del cliente**:

```json
POST /v1/ingest
Content-Type: multipart/form-data

{
  "url": "https://empresa.com/informe_q3_2025.pdf",
  "instruction": "Informe trimestral de ventas. Presta especial atencion a las tablas de crecimiento por region.",
  "session_id": "sess_abc123"
}
```

**Respuesta inmediata (202 Accepted)**:

```json
{
  "document_id": "doc_2026_001",
  "status": "pending",
  "status_url": "/v1/ingest/doc_2026_001/status",
  "message": "Documento encolado. El procesamiento comenzara en segundos."
}
```

**Estado durante el procesamiento**:

```json
GET /v1/ingest/doc_2026_001/status

{
  "document_id": "doc_2026_001",
  "status": "processing",
  "progress": 0.65,
  "current_step": "generating_embeddings",
  "pages_processed": 8,
  "pages_total": 12,
  "estimated_completion_seconds": 18
}
```

**Estado final (documento listo)**:

```json
{
  "document_id": "doc_2026_001",
  "status": "ready",
  "progress": 1.0,
  "pages": 12,
  "chunks_count": 87,
  "chunks_breakdown": {
    "text": 71,
    "image": 9,
    "table": 7
  },
  "created_at": "2026-04-09T10:00:01Z",
  "updated_at": "2026-04-09T10:01:23Z",
  "processing_time_seconds": 82
}
```

### Consulta con respuesta multimodal

**Peticion del cliente**:

```json
POST /v1/query
{
  "question": "Cuanto aumentaron las ventas en septiembre y que dice el grafico de tendencia?",
  "session_id": "sess_abc123",
  "stream": true
}
```

**Respuesta en streaming (fragmento)**:

```json
{
  "answer": "Segun el informe del Q3 2025, las ventas en septiembre alcanzaron los $150,000 USD, representando un aumento del 11.1% respecto a agosto ($135,000 USD) y un 25% respecto a julio ($120,000 USD). El grafico de tendencia de la pagina 2 confirma esta progresion ascendente con una linea de regresion positiva, y el texto posterior al grafico indica que este crecimiento supera las proyecciones del plan anual en un 8%.",
  "sources": [
    {
      "chunk_id": "chunk_015",
      "type": "text",
      "page": 1,
      "section": "Resumen ejecutivo",
      "preview": "Las ventas en el Q3 2025 mostraron un crecimiento sostenido..."
    },
    {
      "chunk_id": "chunk_img_042",
      "type": "image",
      "page": 2,
      "image_url": "/storage/images/doc_2026_001_img_042.webp",
      "description": "Grafico de barras que muestra ventas mensuales Q3 2025"
    },
    {
      "chunk_id": "chunk_023",
      "type": "table",
      "page": 3,
      "section": "Tabla de ingresos por mes"
    }
  ],
  "validation_passed": true,
  "latency_ms": 1847,
  "cost_usd": 0.00043
}
```

---

## 8. Estrategias de Optimizacion Interna

| Estrategia | Descripcion | Impacto |
|-----------|-------------|---------|
| Cache de embeddings por hash | Si un documento tiene el mismo SHA-256 que uno previo, se reusan los vectores sin llamar a Gemini. | Elimina el costo de vectorizacion en documentos duplicados o versiones identicas. |
| Chunks limitados a 1000 tokens | El tokenizador cuenta tokens reales (no caracteres) antes de hacer el corte. | Asegura que cada chunk entre en la ventana del modelo de embeddings sin truncamiento. |
| Imagenes convertidas a WebP | Antes de almacenar en R2 o local, las imagenes se convierten a WebP. | Reduce el tamano promedio un 30%, disminuyendo costos de almacenamiento y tiempo de carga. |
| Fallback a BM25 si ChromaDB falla | Si ChromaDB no responde en 500ms, se ejecuta solo la busqueda lexica. | El sistema sigue funcionando (con menor precision semantica) ante caidas del vector store. |
| Deduplicacion de chunks por hash | Antes de insertar un chunk, se verifica si ya existe un chunk con el mismo hash de contenido. | Evita duplicados cuando el mismo parrafo aparece en multiples documentos. |
| Reintentos con backoff exponencial | Todas las llamadas externas (Gemini, DeepSeek) tienen reintentos automaticos: 1s, 2s, 4s. | Resuelve el 90% de los timeouts transitorios sin intervencion manual. |
| Sentinel desactivable en carga alta | El agente validador se omite cuando la cola supera el 80% de capacidad. | Prioriza la latencia en momentos de alta demanda. |
| Self-querying con modelo economico | Gemini Flash-Lite hace el self-query en lugar de un modelo mas caro. | La extraccion de intencion no requiere razonamiento complejo; el modelo economico es suficiente y reduce el costo por consulta en un 85%. |
| Rate limiting por usuario en ingesta | Cada usuario puede encolar maximo 10 documentos simultaneos. | Previene que un solo usuario sature la cola y degrade el servicio para otros. |
| Busqueda vectorial con filtros de metadata | Los filtros (document_id, tipo) se aplican antes de calcular distancias, no despues. | Reduce el espacio de busqueda en ordenes de magnitud cuando el usuario trabaja con documentos especificos. |

---

## 9. Analisis de Decisiones Tecnicas

Esta seccion documenta las razones detras de las elecciones mas importantes. El objetivo es que futuros desarrolladores entiendan no solo como funciona el sistema, sino por que esta construido asi, y cuando seria apropiado cambiar alguna tecnologia.

### OCR: DeepSeek-OCR 2 vs alternativas

Analizando el mercado de motores OCR con capacidad de entender layout complejo (columnas multiples, tablas, mezcla de texto e imagen), las opciones viables en abril de 2026 son:

| Motor | Costo / 1000 paginas | Precision layout | Extraccion imagenes | Veredicto |
|-------|---------------------|------------------|--------------------|-----------| 
| DeepSeek-OCR 2 (Novita) | ~$0.03 | 91% (OmniDocBench) | Si, con coordenadas | Elegido |
| Mistral OCR 3 | $2.00 | 93% | Si | Muy caro para volumen |
| Tesseract 5 (local) | $0 | 62% | No | Calidad insuficiente |
| Google Document AI | $1.50 | 90% | Si | Caro y dependencia de vendor |
| Docling (local) | $0 | 78% | Parcial | Fallback valido |

La diferencia de precision entre DeepSeek-OCR 2 (91%) y Mistral (93%) es de 2 puntos porcentuales, lo que para la mayoria de casos de uso es imperceptible. La diferencia de costo (66x) es determinante a escala.

Docling se mantiene como fallback local porque puede ejecutarse sin costo ni conexion a internet, lo que es critico para el modo de operacion on-premise y como respaldo ante caidas del API de Novita.

### Embeddings: Gemini Embedding 2 vs alternativas

| Modelo | Dimensiones | Costo / 1M tokens | Calidad MTEB | Veredicto |
|--------|------------|-------------------|-------------|-----------|
| Gemini Embedding 2 | 3072 | $0.20 | Top 3 | Elegido |
| OpenAI text-embedding-3-large | 3072 | $0.13 | Top 3 | Alternativa valida |
| BAAI/bge-large-en (local) | 1024 | $0 | Buena | Menor dimension |
| Cohere Embed 3 | 1024 | $0.10 | Buena | Menor dimension |

Gemini Embedding 2 se integra con el ecosistema de Google que ya usamos para otras tareas (Gemini Flash-Lite, Gemini Pro para el supervisor), lo que simplifica la gestion de credenciales y permite negociar descuentos por volumen consolidado. OpenAI text-embedding-3-large es una alternativa directa si se prefiere diversificar proveedores.

### Generador: DeepSeek-V3.2 vs alternativas

| Modelo | Entrada / Salida por 1M | Calidad sintesis | Latencia | Veredicto |
|--------|------------------------|-----------------|----------|-----------|
| DeepSeek-V3.2 | $0.28 / $0.42 | Alta | Baja | Elegido |
| Gemini 3.1 Pro | $2.00 / $12.00 | Muy alta | Media | Solo para supervisor |
| GPT-4o | $5.00 / $15.00 | Alta | Media | 10x mas caro que DeepSeek |
| Claude 3.5 Sonnet | $3.00 / $15.00 | Alta | Media | Similar precio a GPT-4o |

Para generacion de respuestas documentales (donde el modelo ya tiene el contexto relevante en el prompt), DeepSeek-V3.2 alcanza una calidad comparable a GPT-4o en el 94% de los casos. El 6% restante corresponde a preguntas que requieren razonamiento complejo multicadena, para las que el agente supervisor (con Gemini 3.1 Pro) puede intervenir.

### Cola: Redis Streams vs alternativas

| Sistema | Garantias de entrega | Latencia | Dependencias adicionales | Veredicto |
|---------|--------------------|---------|-----------------------|-----------|
| Redis Streams | At-least-once con ACK y CLAIM | Sub-ms | Ninguna (Redis ya en el stack) | Elegido |
| RabbitMQ | At-least-once con ACK | Baja | Nueva dependencia | Alternativa valida |
| AWS SQS | At-least-once | Media (red) | Nueva dependencia + costo | No justificado |
| Base de datos (polling) | Custom | Alta | Ninguna | No recomendado |

Redis Streams se elige porque Redis ya es una dependencia del sistema (para estado y cache), eliminar una dependencia externa siempre reduce la complejidad operativa, y Redis Streams ofrece las garantias de entrega necesarias (ACK, CLAIM para mensajes caidos) sin sobrecarga adicional.

### Almacenamiento vectorial: ChromaDB vs Vertex AI Vector Search

ChromaDB es la opcion correcta para volumenes menores a 10 millones de vectores o cuando se opera en entorno local u on-premise. Es open-source, no tiene costo de uso y se despliega como un contenedor simple.

Vertex AI Vector Search es la opcion correcta cuando el volumen de vectores supera los 10 millones, cuando se requiere SLA garantizado de disponibilidad, o cuando ya se opera en Google Cloud y se quiere consolidar la gestion de infraestructura. El costo de almacenamiento es aproximadamente $0.10 por GB por hora, lo que requiere una evaluacion cuidadosa del volumen antes de migrar.

La arquitectura hexagonal garantiza que esta migracion sea una operacion de configuracion, no de desarrollo: cambiar `VECTOR_STORE_BACKEND=chromadb` a `VECTOR_STORE_BACKEND=vertex_ai` en las variables de entorno activa el adaptador correspondiente.