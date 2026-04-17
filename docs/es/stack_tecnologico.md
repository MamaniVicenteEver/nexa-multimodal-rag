# Especificacion del Stack Tecnologico: Nexa Multimodal RAG

Diseno y documentacion de una arquitectura RAG multimodal basada en principios de Arquitectura Hexagonal. Este sistema esta optimizado para la eficiencia de costos, la escalabilidad y el procesamiento inteligente de documentos estructurados mediante modelos de vision, embeddings y LLMs avanzados.

---

## 1. Modelos de Extraccion y Vision (OCR)

### DeepSeek-OCR 2 (via Novita AI)
* **Rol en el Sistema:** Motor principal de extraccion. Encargado del analisis estructural profundo de los documentos PDF, interpretando el layout, extrayendo tablas y determinando el orden de lectura correcto.
* **Capacidades:** Transforma paginas complejas utilizando la arquitectura DeepEncoder V2. Requiere entre 256 y 1120 tokens visuales por pagina.
* **Documentacion Oficial:** [DeepSeek-OCR 2 Docs](https://novita.ai/models/model-detail/deepseek-deepseek-ocr-2)
* **Precios Oficiales:** [Novita AI Pricing](https://novita.ai/pricing)
* **Estructura de Costos (Pago por uso):**
  * Entrada (Texto/Imagen): $0.03 USD / 1M Tokens
  * Salida (Texto): $0.03 USD / 1M Tokens

---

## 2. Modelos de Vectorizacion Multimodal (Embeddings)

### Gemini Embedding 2 Preview (gemini-embedding-2-preview)
* **Rol en el Sistema:** Motor matematico de la base de datos vectorial. Convierte textos limpios y descripciones en vectores de hasta 3,072 dimensiones.
* **Documentacion Oficial:** [Gemini Embedding 2 Docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/embedding-2)
* **Estructura de Costos:**
  * Nivel Gratuito: Sin costo (Google AI Studio).
  * Nivel de Pago (PayGo):
    * Entrada de Texto: $0.20 USD / 1M Tokens
    * Entrada de Imagen: $0.45 USD / 1M Tokens
    * Entrada de Audio: $6.50 USD / 1M Tokens
    * Entrada de Video: $12.00 USD / 1M Tokens

---

## 3. Ecosistema de Modelos de Lenguaje (LLMs)

### Gemini 3.1 Flash-Lite (gemini-3.1-flash-lite-preview)
* **Rol en el Sistema:** Enrutador Cognitivo (Self-Querying) y Procesador de Ingesta. Optimizado para tareas de agentes de gran volumen y extraccion de datos simple.
* **Capacidades:** Soporte multimodal con una ventana de contexto de 1,048,576 tokens de entrada. Soporta API por lotes, busqueda de archivos y salidas estructuradas.
* **Documentacion Oficial:** [Gemini 3.1 Flash-Lite Docs](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite-preview)
* **Estructura de Costos:**
  * Nivel Gratuito: Disponible.
  * Nivel de Pago (Por 1M de tokens):
    * Entrada: $0.25 USD (texto, imagen o video) | $0.50 USD (audio)
    * Salida: $1.50 USD (incluidos los tokens de pensamiento)
    * Almacenamiento de contexto en cache: $0.025 USD (texto, imagen o video) | $0.05 USD (audio) | $1.00 USD por 1M tokens/hora.
    * Fundamentacion con Busqueda/Maps: 5,000 instrucciones por mes sin cargo; luego $14.00 USD por cada 1,000 busquedas.

### Gemini 3.1 Flash Live (gemini-3.1-flash-live-preview)
* **Rol en el Sistema:** Interfaz de Voz Bidireccional (Expansion Futura). Modelo de audio a audio de baja latencia optimizado para el dialogo en tiempo real con deteccion de matices acusticos.
* **Documentacion Oficial:** [Gemini 3.1 Flash Live Docs](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-live)
* **Estructura de Costos:**
  * Nivel Gratuito: Disponible.
  * Nivel de Pago (Por 1M de tokens):
    * Entrada: $0.75 USD (texto) | $3.00 USD o $0.005/min (audio) | $1.00 USD o $0.002/min (imagen o video)
    * Salida: $4.50 USD (texto) | $12.00 USD o $0.018/min (audio)
    * Fundamentacion con Busqueda: 5,000 instrucciones por mes sin cargo; luego $14.00 USD por cada 1,000 busquedas.

### DeepSeek-V3.2 (Chat & Reasoner)
* **Rol en el Sistema:** Sintetizador Final. Recibe el contexto estructurado recuperado de las bases de datos (Dual Retrieval) y redacta la respuesta tecnica definitiva.
* **Documentacion Oficial:** [DeepSeek Platform Docs](https://platform.deepseek.com/)
* **Estructura de Costos (Pago por uso):**
  * Entrada (Cache Hit): $0.028 USD / 1M Tokens
  * Entrada (Cache Miss): $0.28 USD / 1M Tokens
  * Salida: $0.42 USD / 1M Tokens

---

## 4. Infraestructura de Busqueda y Persistencia

### ChromaDB
* **Rol en el Sistema:** Base de datos vectorial principal. Almacena los vectores multimodales y ejecuta busquedas por similitud semantica.
* **Documentacion Oficial:** [ChromaDB Docs](https://docs.trychroma.com/)
* **Estructura de Costos:** $0.00 USD (Despliegue Local / Open Source).

### BM25 (Libreria rank_bm25)
* **Rol en el Sistema:** Motor de busqueda lexica operando en paralelo con ChromaDB (Dual Retrieval).
* **Documentacion Oficial:** [BM25 PyPI](https://pypi.org/project/rank-bm25/)
* **Estructura de Costos:** $0.00 USD (Despliegue Local / Open Source).

---

## 5. Frameworks de Desarrollo Backend

### FastAPI & Pydantic
* **Rol en el Sistema:** Framework de enrutamiento asincrono y validacion estricta de contratos de datos.
* **Estructura de Costos:** $0.00 USD (Open Source).

---

## Consideraciones Operativas

Los precios detallados corresponden a las tarifas oficiales de las plataformas proveedoras. Es obligatorio monitorear las cuotas de uso y las llaves de API desde el gestor de variables de entorno del sistema para evitar sobrecostos en entornos de produccion a gran escala.

---
# Arquitectura y Autoria

**Autor y Arquitecto de Software:** Ever Mamani Vicente

**Contacto y Colaboraciones:** evermamanivicente@gmail.com

**Version del Documento:** v1.1.0

**Fecha de Documentacion:** Abril 2026