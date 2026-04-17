
# Arquitectura del Sistema RAG Multimodal (Grado Industrial)

**Proyecto:** Nexa Multimodal RAG  
**Descripción:** Motor de Búsqueda Semántica y Generación Aumentada por Recuperación (RAG) diseñado para procesar y consultar documentos complejos de alta fidelidad.

<p align="left">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/DeepSeek_OCR_2-4D4D4D?style=flat-square&logo=deepseek&logoColor=white" alt="DeepSeek" />
  <img src="https://img.shields.io/badge/Gemini_3.1-4285F4?style=flat-square&logo=google&logoColor=white" alt="Gemini" />
  <img src="https://img.shields.io/badge/ChromaDB-FF6F00?style=flat-square&logo=data&logoColor=white" alt="ChromaDB" />
  <img src="https://img.shields.io/badge/BM25-000000?style=flat-square&logo=elasticsearch&logoColor=white" alt="BM25" />
</p>

Este documento detalla los dos macro-flujos que componen el sistema: el **Flujo de Ingesta (Offline)** y el **Flujo de Consulta (Online)**, junto con un análisis técnico de la inyección de dependencias.

---

## 1. Macro-Bloque A: Pipeline de Ingesta y Entrenamiento (Offline)

Flujo asíncrono diseñado para evitar el principio GIGO (*Garbage In, Garbage Out*) mediante limpieza exhaustiva y enriquecimiento semántico antes de la vectorización en la base de datos.

### Diagrama del Flujo de Ingesta

```mermaid
graph TD
    classDef doc fill:#1e293b,stroke:#94a3b8,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef extract fill:#0284c7,stroke:#0369a1,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef clean fill:#be185d,stroke:#9d174d,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef enrich fill:#6d28d9,stroke:#4c1d95,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef embed fill:#059669,stroke:#047857,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef db fill:#0f766e,stroke:#115e59,stroke-width:2px,color:#fff,rx:10,ry:10;

    subgraph FASE_1 ["1. ENTRADA Y EXTRACCION ESTRUCTURAL"]
        direction TB
        Input1["Documentos Complejos<br>Tech: PDF / Docx"]:::doc
        Input2["Textos Planos<br>Tech: TXT / MD"]:::doc
        
        OCR["Extractor Estructural Avanzado<br>Tech: DeepSeek-OCR 2 (API) / Docling<br>Accion: Extraccion de Markdown y Layout"]:::extract
        Parser["Lector Nativo<br>Tech: Python utf-8<br>Accion: Lectura de texto plano"]:::extract
        
        Input1 --> OCR
        Input2 --> Parser
    end

    subgraph FASE_2 ["2. LIMPIEZA Y NORMALIZACION"]
        direction TB
        RawTxt["Texto en Markdown"]:::doc
        RawImg["Imagenes Extraidas"]:::doc
        
        OCR --> RawTxt & RawImg
        Parser --> RawTxt
        
        TxtClean["Sanitizador de Texto<br>Tech: Python Regex<br>Accion: Une saltos rotos, borra footers"]:::clean
        TxtNorm["Normalizador de Texto<br>Tech: Reglas Logicas<br>Accion: Estandariza fechas ISO"]:::clean
        ImgClean["Filtro Visual<br>Tech: Python PIL / Hashing MD5<br>Accion: Elimina logos repetidos"]:::clean

        RawTxt --> TxtClean --> TxtNorm
        RawImg --> ImgClean
    end

    subgraph FASE_3 ["3. CHUNKING Y ENRIQUECIMIENTO SEMANTICO"]
        direction TB
        Chunker["Semantic Chunker<br>Tech: RecursiveTextSplitter<br>Accion: Segmentacion por ideas"]:::enrich
        
        CtxLLM["Contextualizador<br>Tech: Gemini 3.1 Flash-Lite<br>Accion: Inyeccion de resumen global"]:::enrich
        MetaLLM["Extractor de Metadatos<br>Tech: LLM + Regex<br>Accion: Extrae tags duros"]:::enrich
        Vision["Analista de Vision<br>Tech: Gemini 3.1 Flash-Lite<br>Accion: Descripcion tecnica visual"]:::enrich

        TxtNorm --> Chunker
        Chunker --> CtxLLM & MetaLLM
        ImgClean --> Vision
        
        RichChunk["Chunk Enriquecido<br>Texto + Contexto"]:::doc
        RichImg["Imagen Enriquecida<br>Base64 + Descripcion"]:::doc
        
        CtxLLM & MetaLLM --> RichChunk
        Vision --> RichImg
    end

    subgraph FASE_4 ["4. VECTORIZACION Y ALMACENAMIENTO DUAL"]
        direction TB
        Embedder["Generador de Vectores<br>Tech: gemini-embedding-2-preview<br>Accion: Espacio de 3072 dimensiones"]:::embed
        
        RichChunk & RichImg --> Embedder
        
        VectorDB["Base de Datos Vectorial<br>Tech: ChromaDB<br>Almacena: Vectores + Metadatos"]:::db
        LexicalDB["Indice Lexico<br>Tech: BM25<br>Almacena: Busqueda exacta"]:::db
        Disk["File System<br>Tech: Disco Local<br>Almacena: Imagenes fisicas"]:::db
        
        Embedder --> VectorDB
        RichChunk --> LexicalDB
        RichImg --> Disk
    end
```

---

## 2. Macro-Bloque B: Flujo de Consulta y Respuesta (Online)

Ejecución en tiempo real para resolver interacciones de usuario mediante Dual Retrieval y Re-Ranking.

### Diagrama del Flujo de Consulta

```mermaid
graph TD
    classDef input fill:#1e293b,stroke:#94a3b8,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef router fill:#d97706,stroke:#b45309,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef db fill:#0f766e,stroke:#115e59,stroke-width:2px,color:#fff,rx:10,ry:10;
    classDef search fill:#0284c7,stroke:#0369a1,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef rerank fill:#b45309,stroke:#78350f,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef gen fill:#059669,stroke:#047857,stroke-width:2px,color:#fff,rx:8,ry:8;

    subgraph ETAPA_1 ["1. AUTO-ANALISIS DE LA CONSULTA"]
        direction TB
        User["Reclutador / Usuario<br>Tech: Frontend Client<br>Accion: Query Natural"]:::input
        
        SelfQuery["Motor Self-Querying<br>Tech: Gemini 3.1 Flash-Lite<br>Accion: Parsed Query"]:::router
        
        Intent["Intencion Semantica"]:::input
        KeyW["Palabras Clave (Keywords)"]:::input
        Filter["Filtros Metadata"]:::input

        User --> SelfQuery
        SelfQuery --> Intent & KeyW & Filter
    end

    subgraph ETAPA_2 ["2. RECUPERACION HIBRIDA (DUAL RETRIEVAL)"]
        direction TB
        Embedder["Vectorizador<br>Tech: Gemini Embeddings 2"]:::gen
        
        Intent --> Embedder
        
        VectorSearch["Busqueda Vectorial<br>Tech: ChromaDB"]:::db
        LexicalSearch["Busqueda Lexica<br>Tech: BM25"]:::db

        Embedder --> VectorSearch
        Filter -.->|WHERE clause| VectorSearch
        KeyW --> LexicalSearch
        
        Merge["Fusion RRF<br>Tech: Reciprocal Rank Fusion<br>Accion: Combina y deduplica"]:::search
        
        VectorSearch & LexicalSearch --> Merge
    end

    subgraph ETAPA_3 ["3. RE-RANKING"]
        direction TB
        ReRanker["Cross-Encoder<br>Tech: HuggingFace bge-reranker"]:::rerank
        TopK["Seleccion Top-K<br>Accion: Filtro de alta precision"]:::rerank
        
        Merge --> ReRanker --> TopK
    end

    subgraph ETAPA_4 ["4. SINTESIS MULTIMODAL"]
        direction TB
        History["Memoria de Chat<br>Accion: Contexto previo"]:::input
        
        Prompt["Ensamblador de Prompt<br>Accion: Contexto + Historial + Query"]:::gen
        
        TopK --> Prompt
        History --> Prompt
        
        FinalLLM["Sintetizador Final<br>Tech: DeepSeek-V3.2 / Gemini<br>Accion: Generacion de Respuesta"]:::gen
        Streaming["Streaming SSE<br>Tech: FastAPI<br>Accion: Respuesta en tiempo real"]:::gen
        
        Prompt --> FinalLLM --> Streaming --> User
    end
```

---

## 3. Análisis Arquitectónico: Reemplazo del Motor OCR

La transición de **Mistral OCR 3** a **DeepSeek-OCR 2** (o una librería local como **Docling**) pone a prueba la resiliencia del diseño Hexagonal. A continuación, se detalla el impacto técnico de este cambio en el sistema.

### 3.1. Impacto en el Dominio (Cero Acoplamiento)
El núcleo de la aplicación (`src/core/`) no sufre ninguna modificación. El contrato `IOCRProvider` y las entidades (`Document`, `TextChunk`, `ImageChunk`) permanecen inmutables. El sistema central no sabe, ni le importa, si el texto fue extraído por una API costosa o por un script local. 

### 3.2. Adaptación de la Capa de Infraestructura
El único cambio real ocurre en la capa de infraestructura. Se requiere la creación de un nuevo adaptador `src/infrastructure/ocr/deepseek_client.py` que implemente la interfaz `IOCRProvider`.
* **Traducción de Payloads:** DeepSeek-OCR 2 utiliza la arquitectura *DeepEncoder V2* (Qwen2-0.5B). El adaptador debe encargarse de mapear la respuesta JSON de la API de Novita (o el output de Docling) hacia nuestra entidad estandarizada de Markdown interno.
* **Manejo de Imágenes:** Si el nuevo proveedor OCR no devuelve las imágenes recortadas en Base64 (como lo hacía Mistral), el adaptador deberá incorporar lógica adicional (ej. PyMuPDF) para extraer las coordenadas dadas por el OCR y recortar las imágenes localmente antes de pasarlas al pipeline.

### 3.3. Impacto en Rendimiento y Costos
* **Latencia:** Al utilizar Novita API (Serverless), la latencia de red se mantiene. Si se opta por Docling (local), la latencia dependerá del hardware del servidor donde se despliegue FastAPI, eliminando el tiempo de espera por red pero aumentando el consumo de CPU/RAM.
* **Eficiencia Financiera:** El cambio a DeepSeek-OCR 2 reduce el costo drásticamente de $2.00 USD por 1000 páginas a aproximadamente $0.06 USD por millón de tokens, optimizando el presupuesto del pipeline offline.

### 3.4. Inyección de Dependencias (El Switch)
Gracias a `Dependency Injection`, el cambio en el código de producción se reduce a modificar una sola línea en el enrutador principal (`routes.py` o `container.py`):

```python
# ANTES:
# ocr_service = MistralOCRClient(api_key=settings.MISTRAL_API_KEY)

# DESPUÉS:
ocr_service = DeepSeekOCRClient(api_key=settings.NOVITA_API_KEY)

# El orquestador recibe la nueva dependencia sin necesidad de reescribir la lógica de negocio
use_case = IngestDocumentUseCase(ocr_provider=ocr_service, ...)
```

---

**Autor y Arquitecto de Software:** Ever Mamani Vicente  
**Contacto Profesional:** evermamanivicente@gmail.com  
**Versión del Documento:** v1.2.0 | Abril 2026  
```
