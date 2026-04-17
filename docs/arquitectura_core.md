# 🏗️ Arquitectura del Sistema RAG Multimodal (Grado Industrial)

**Proyecto:** Nexa Multimodal RAG  
**Descripción:** Motor de Búsqueda Semántica y Generación Aumentada por Recuperación (RAG) diseñado para procesar y consultar documentos complejos (texto e imágenes) de alta fidelidad.

Este documento detalla los dos macro-flujos que componen el sistema: el **Flujo de Ingesta (Offline)**, encargado de la preparación y enriquecimiento de los datos, y el **Flujo de Consulta (Online)**, que gestiona la recuperación dinámica y síntesis de respuestas.

---

## 📥 1. Macro-Bloque A: Pipeline de Ingesta y Entrenamiento (Offline)

Este flujo se ejecuta de manera asíncrona cuando se añaden nuevos documentos (manuales, currículums, reportes de proyectos) al sistema. Su objetivo es evitar el principio GIGO (*Garbage In, Garbage Out*) mediante limpieza exhaustiva y enriquecimiento semántico antes de la vectorización.

### Diagrama del Flujo de Ingesta

```mermaid
graph TD
    classDef doc fill:#1e293b,stroke:#94a3b8,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef extract fill:#0284c7,stroke:#0369a1,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef clean fill:#be185d,stroke:#9d174d,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef enrich fill:#6d28d9,stroke:#4c1d95,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef embed fill:#059669,stroke:#047857,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef db fill:#0f766e,stroke:#115e59,stroke-width:2px,color:#fff,rx:10,ry:10;

    subgraph FASE_1 ["📥 1. ENTRADA Y EXTRACCIÓN ESTRUCTURAL"]
        direction TB
        Input1["📄 Documentos Complejos<br>Tech: PDF / Docx<br>Info: Manuales, CV, Proyectos"]:::doc
        Input2["📝 Textos Planos<br>Tech: TXT / MD<br>Info: Notas, Código crudo"]:::doc
        
        OCR["🔍 Extractor Estructural<br>Tech: Mistral OCR 3 API<br>Acción: Convierte PDF a Markdown e imágenes Base64"]:::extract
        Parser["🐍 Lector Nativo<br>Tech: Python utf-8<br>Acción: Lee el texto directamente"]:::extract
        
        Input1 --> OCR
        Input2 --> Parser
    end

    subgraph FASE_2 ["🧹 2. LIMPIEZA Y NORMALIZACIÓN (GIGO)"]
        direction TB
        RawTxt["Texto en Markdown"]:::doc
        RawImg["Imágenes Extraídas"]:::doc
        
        OCR --> RawTxt & RawImg
        Parser --> RawTxt
        
        TxtClean["🛠️ Sanitizador de Texto<br>Tech: Python Regex<br>Acción: Une saltos de línea rotos, borra footers y PII"]:::clean
        TxtNorm["📏 Normalizador de Texto<br>Tech: Reglas Lógicas<br>Acción: Estandariza fechas (ISO) y unidades"]:::clean
        ImgClean["🖼️ Filtro Visual<br>Tech: Python PIL / Hashing MD5<br>Acción: Elimina logos repetidos e iconos < 50px"]:::clean

        RawTxt --> TxtClean --> TxtNorm
        RawImg --> ImgClean
    end

    subgraph FASE_3 ["🧠 3. CHUNKING Y ENRIQUECIMIENTO SEMÁNTICO"]
        direction TB
        Chunker["✂️ Semantic Chunker<br>Tech: LangChain TextSplitter<br>Acción: Corta texto manteniendo ideas completas"]:::enrich
        
        CtxLLM["🤖 Contextualizador<br>Tech: Gemini 2.5 Flash<br>Acción: Añade resumen global al inicio de cada chunk"]:::enrich
        MetaLLM["🏷️ Extractor de Metadatos<br>Tech: Gemini / Regex<br>Acción: Extrae {año, tecnologías, proyecto}"]:::enrich
        Vision["👁️ Analista de Visión<br>Tech: Gemini Vision<br>Acción: Crea descripción técnica de la imagen"]:::enrich

        TxtNorm --> Chunker
        Chunker --> CtxLLM & MetaLLM
        ImgClean --> Vision
        
        RichChunk["Chunk Enriquecido<br>Texto + Contexto + Metadatos"]:::doc
        RichImg["Imagen Enriquecida<br>Base64 + Descripción Semántica"]:::doc
        
        CtxLLM & MetaLLM --> RichChunk
        Vision --> RichImg
    end

    subgraph FASE_4 ["🔢 4. VECTORIZACIÓN Y ALMACENAMIENTO HÍBRIDO"]
        direction TB
        Embedder["🔢 Generador de Vectores<br>Tech: Gemini text-embedding-004<br>Acción: Convierte texto a espacio geométrico (768d)"]:::embed
        
        RichChunk & RichImg --> Embedder
        
        VectorDB["🗃️ Base de Datos Vectorial<br>Tech: ChromaDB<br>Almacena: Vectores + Metadatos"]:::db
        LexicalDB["📚 Índice Léxico<br>Tech: BM25 / ElasticSearch<br>Almacena: Texto crudo para búsqueda exacta"]:::db
        Disk["📁 File System<br>Tech: Disco Local OS<br>Almacena: Imágenes reales .jpg/.png"]:::db
        
        Embedder --> VectorDB
        RichChunk --> LexicalDB
        RichImg --> Disk
    end
```

### Explicación de las Fases (Ingesta)
* **Fase 1: Extracción.** Uso de Mistral OCR 3 para transformar documentos no estructurados en Markdown limpio, extrayendo las imágenes sin perder la estructura lógica (tablas, títulos).
* **Fase 2: Limpieza.** Aplicación de expresiones regulares y algoritmos de deduplicación para eliminar basura técnica (encabezados repetitivos, iconos diminutos) que diluye la precisión matemática de los vectores.
* **Fase 3: Enriquecimiento (Contextual Chunking).** La fase crítica. Cada fragmento de texto recibe un resumen global (inyectado por un LLM rápido) para no perder el contexto de qué trata el documento. Se extraen metadatos duros para habilitar filtros SQL-like posteriores.
* **Fase 4: Almacenamiento Dual.** Los datos se guardan tanto en un espacio vectorial (ChromaDB) para búsqueda por significado, como en un índice léxico (BM25) para búsquedas de coincidencias exactas.

---

## 🚀 2. Macro-Bloque B: Flujo de Consulta y Respuesta (Online)

Este flujo ocurre en tiempo real (latencia de milisegundos a segundos) cuando el usuario o reclutador interactúa con el sistema mediante una pregunta en lenguaje natural.

### Diagrama del Flujo de Consulta

```mermaid
graph TD
    classDef input fill:#1e293b,stroke:#94a3b8,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef router fill:#d97706,stroke:#b45309,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef db fill:#0f766e,stroke:#115e59,stroke-width:2px,color:#fff,rx:10,ry:10;
    classDef search fill:#0284c7,stroke:#0369a1,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef rerank fill:#b45309,stroke:#78350f,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef gen fill:#059669,stroke:#047857,stroke-width:2px,color:#fff,rx:8,ry:8;

    subgraph ETAPA_1 ["💬 1. INTERACCIÓN Y AUTO-ANÁLISIS DE LA CONSULTA"]
        direction TB
        User["🧑‍💻 Reclutador<br>Tech: Interfaz Gradio / React<br>Acción: Pregunta: '¿Proyectos en Python en 2025?'"]:::input
        
        SelfQuery["🧠 Motor Self-Querying<br>Tech: LLM + LangChain<br>Acción: Divide la intención humana en comandos de máquina"]:::router
        
        Intent["🎯 Intención Semántica<br>'Proyectos de desarrollo'"]:::input
        KeyW["🔑 Palabras Clave<br>'Python'"]:::input
        Filter["⚙️ Filtros Duros<br>Metadata: {año: 2025}"]:::input

        User --> SelfQuery
        SelfQuery --> Intent & KeyW & Filter
    end

    subgraph ETAPA_2 ["🔍 2. RECUPERACIÓN HÍBRIDA (DUAL RETRIEVAL)"]
        direction TB
        Embedder["🔢 Vectorizador On-the-fly<br>Tech: Gemini Embeddings 2<br>Acción: Vectoriza la Intención Semántica"]:::gen
        
        Intent --> Embedder
        
        VectorSearch["🗃️ Búsqueda Vectorial<br>Tech: ChromaDB (Similitud Coseno)<br>Acción: Busca Top 15 textos + Top 5 imágenes"]:::db
        LexicalSearch["📚 Búsqueda Léxica<br>Tech: Índice BM25<br>Acción: Busca Top 15 coincidencias exactas"]:::db

        Embedder --> VectorSearch
        Filter -.->|Aplica filtro WHERE| VectorSearch
        KeyW --> LexicalSearch
        
        Merge["🤝 Fusión de Resultados<br>Tech: Reciprocal Rank Fusion (RRF)<br>Acción: Combina listas y elimina duplicados"]:::search
        
        VectorSearch & LexicalSearch --> Merge
    end

    subgraph ETAPA_3 ["🔥 3. RE-RANKING Y ALTA PRECISIÓN"]
        direction TB
        ReRanker["⚖️ Cross-Encoder Re-Ranker<br>Tech: bge-reranker (HuggingFace)<br>Acción: Lee la pregunta + los 30 fragmentos fusionados"]:::rerank
        
        Score["💯 Puntuación de Relevancia<br>Acción: Asigna nota del 0 al 1 a cada fragmento"]:::rerank
        TopK["🥇 Selección 'Oro'<br>Acción: Se queda solo con los Top 4 Chunks que SÍ responden"]:::rerank
        
        Merge --> ReRanker --> Score --> TopK
    end

    subgraph ETAPA_4 ["✨ 4. CONSTRUCCIÓN DE PROMPT Y RESPUESTA MULTIMODAL"]
        direction TB
        History["⏱️ Historial de Chat<br>Tech: Memoria de Gradio<br>Acción: Provee contexto de la charla"]:::input
        ImagesDir["📁 File System<br>Tech: Lector Python<br>Acción: Carga las imágenes asociadas en Base64"]:::db
        
        Prompt["📝 Ensamblador de Prompt<br>Tech: Python Textwrap<br>Acción: Une Historial + Top 4 Textos + Imágenes Físicas"]:::gen
        
        TopK --> Prompt
        History & ImagesDir --> Prompt
        
        FinalLLM["🤖 Sintetizador Final<br>Tech: Gemini 2.5 Flash / DeepSeek<br>Acción: Analiza texto+imagen y redacta respuesta"]:::gen
        Streaming["⚡ Streaming SSE<br>Tech: FastAPI<br>Acción: Devuelve texto palabra por palabra + Tarjetas de imagen"]:::gen
        
        Prompt --> FinalLLM --> Streaming -->|Muestra al Reclutador| User
    end
```

### Explicación de las Fases (Consulta)
* **Etapa 1: Self-Querying.** En lugar de buscar directamente lo que escribió el usuario, un LLM actúa como router. Si el usuario pide algo del "2025", el motor lo extrae como un filtro metadata determinista para evitar búsquedas semánticas ineficientes.
* **Etapa 2: Búsqueda Híbrida.** Se atacan dos frentes simultáneos. ChromaDB busca por "significado" y BM25 busca por "coincidencia de texto" para cubrir términos técnicos y acrónimos.
* **Etapa 3: Re-Ranking.** El paso clave para la alta precisión. Un modelo Cross-Encoder evalúa los resultados amplios (top 30) y los puntúa exhaustivamente contra la pregunta original, dejando pasar solo el contexto dorado al prompt final (Top 4).
* **Etapa 4: Generación Multimodal.** Se ensambla el contexto histórico, los chunks de texto dorados y las imágenes físicas relacionadas. El LLM sintetiza la respuesta y la emite hacia el cliente vía Server-Sent Events (Streaming), mostrando texto e interfaz gráfica enriquecida.
```