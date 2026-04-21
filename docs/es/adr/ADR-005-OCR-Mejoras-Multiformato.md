# ADR-005: Mejoras en el Motor de Extracción Multiformato y OCR

**Estado:** Aceptado e Implementado

**Fecha:** 2026-04-21

## Contexto y Problema

El sistema Nexa RAG inicialmente solo soportaba archivos PDF e imágenes. Para ampliar la utilidad del sistema y permitir la ingesta de catálogos de productos, documentos Word, datos estructurados y texto plano, era necesario extender el pipeline de extracción. Además, el orquestador de PDF (`HybridDocumentProcessor`) inyectaba cabeceras decorativas (`==== PÁGINA X ====`) que contaminaban los vectores y dificultaban la trazabilidad limpia.

## Decisión

Implementar un **Extractor de Documentos Unificado (`DocumentExtractor`)** que enruta cada tipo de archivo al procesador adecuado y devuelve una estructura de datos común: `ExtractedPage`. Esta estructura separa el contenido textual (limpio, sin cabeceras) de los metadatos de página (número, tipo de procesamiento, URLs de imágenes). Se añadió soporte para **DOCX, TXT, MD y JSON**, además de los existentes PDF e imágenes.

## Cambios Realizados

### 1. Nueva entidad `ExtractedPage`
- **Ubicación:** `src/core/domain/extracted_page.py`
- **Atributos:** `page_number`, `content` (Markdown limpio), `page_type` (`LOCAL`, `OCR`, `TEXT`, etc.), `image_urls`, `metadata`.
- **Propósito:** Desacoplar la presentación (cabeceras) del contenido real, permitiendo que los chunks hereden metadatos sin ruido.

### 2. Refactorización de `HybridDocumentProcessor`
- Ya no concatena strings con cabeceras. Devuelve `List[ExtractedPage]`.
- Las páginas omitidas se incluyen con `content=""` y `page_type="OMITIDA"`.
- El debug final se guarda con comentarios HTML (`<!-- PÁGINA X -->`) para legibilidad sin contaminar vectores.

### 3. Nuevo `DocumentExtractor`
- **Ubicación:** `src/modules/ingestion/document_extractor.py`
- Soporte para:
  - **PDF:** Delegación a `HybridDocumentProcessor`.
  - **DOCX:** Extracción local con `python-docx`, convirtiendo estilos a Markdown.
  - **Imágenes:** OCR directo.
  - **Texto/Markdown/JSON:** Lectura directa; JSON se formatea como texto legible o se mantiene crudo para `EntityChunker`.
- **Ventaja:** Un único punto de entrada para cualquier formato, facilitando la adición de nuevos tipos en el futuro.

### 4. Inyección de metadatos de página en chunks
- En `service.py`, cada `ExtractedPage` aporta `base_metadata` (`page_number`, `page_type`) que se propaga a todos los chunks de esa página (tanto texto como imágenes).
- Los chunks de imagen también reciben estos metadatos mediante `img_chunk.metadata.update(base_metadata)`.

## Impacto

- **Vectores más limpios:** Sin líneas de `====` ni emojis de página, mejorando la precisión de búsqueda semántica.
- **Trazabilidad mejorada:** El frontend puede mostrar "Página 2 (OCR)" usando los metadatos, sin necesidad de parsear el contenido del chunk.
- **Extensibilidad:** Añadir un nuevo formato (ej. `.epub`, `.csv`) solo requiere extender `DocumentExtractor` y, opcionalmente, un procesador específico.
- **Soporte para catálogos:** Gracias al manejo de JSON y la estrategia `EntityChunker`, ahora es posible indexar productos con imágenes asociadas.

## Consideraciones Futuras

- Podría integrarse un extractor para `.csv` que convierta filas en entidades automáticamente.
- Para documentos Word muy complejos (con muchas tablas anidadas), podría considerarse un paso intermedio de conversión a PDF y luego OCR, aunque el coste sería mayor.