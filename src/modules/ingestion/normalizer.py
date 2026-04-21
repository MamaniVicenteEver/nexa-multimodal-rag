"""
Normalizador de texto para limpieza post-extracción.

Aplica reglas de limpieza y formateo para eliminar ruido introducido por
el OCR o por la conversión de formatos, dejando el texto listo para el
chunking semántico y la vectorización.
"""

import re
from src.shared.logging import get_logger

logger = get_logger("text_normalizer")


class TextNormalizer:
    """
    Limpia y normaliza texto aplicando reglas configurables.

    Uso típico:
        normalizer = TextNormalizer()
        clean_text = normalizer.normalize(raw_markdown)
    """

    def __init__(
        self,
        remove_excessive_newlines: bool = True,
        max_consecutive_newlines: int = 2,
        remove_control_chars: bool = True,
        normalize_whitespace: bool = True,
    ):
        """
        Args:
            remove_excessive_newlines: Si es True, reduce secuencias de saltos de línea.
            max_consecutive_newlines: Número máximo de saltos de línea consecutivos permitidos.
            remove_control_chars: Elimina caracteres de control no imprimibles (excepto \n, \t).
            normalize_whitespace: Reemplaza múltiples espacios/tabs por uno solo.
        """
        self.remove_excessive_newlines = remove_excessive_newlines
        self.max_consecutive_newlines = max_consecutive_newlines
        self.remove_control_chars = remove_control_chars
        self.normalize_whitespace = normalize_whitespace

    def normalize(self, text: str) -> str:
        """
        Aplica la secuencia completa de limpieza al texto de entrada.
        """
        if not text:
            return ""

        original_length = len(text)
        logger.debug(f"Iniciando normalización de {original_length} caracteres")

        # 1. Eliminar caracteres de control (excepto saltos de línea y tabulaciones)
        if self.remove_control_chars:
            # Mantenemos \n (salto de línea) y \t (tabulación)
            text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        # 2. Normalizar saltos de línea excesivos
        if self.remove_excessive_newlines:
            pattern = r'\n{' + str(self.max_consecutive_newlines + 1) + r',}'
            text = re.sub(pattern, '\n' * self.max_consecutive_newlines, text)

        # 3. Eliminar espacios en blanco al final de cada línea
        text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)

        # 4. Reemplazar múltiples espacios/tabs por un solo espacio
        if self.normalize_whitespace:
            # Cuidado: no queremos colapsar los saltos de línea
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                # Colapsar espacios múltiples dentro de la línea
                line = re.sub(r'[ \t]{2,}', ' ', line)
                cleaned_lines.append(line)
            text = '\n'.join(cleaned_lines)

        # 5. Eliminar líneas que son claramente artefactos de OCR (opcional)
        text = self._remove_garbage_lines(text)

        # 6. Eliminar espacios al inicio y final del documento
        text = text.strip()

        logger.debug(f"Normalización completada: {original_length} -> {len(text)} caracteres")
        return text

    def _remove_garbage_lines(self, text: str) -> str:
        """
        Elimina líneas que contienen solo ruido (coordenadas residuales, números sueltos, etc.).
        """
        lines = text.split('\n')
        filtered = []

        for line in lines:
            stripped = line.strip()

            # Conservar líneas vacías (estructura)
            if not stripped:
                filtered.append('')
                continue

            # 1. Líneas que son coordenadas de bounding box (ej: "[[123, 456, 789, 012]]")
            if re.match(r'^\[\[\d+.*\]\]$', stripped):
                continue

            # 2. Líneas que contienen solo números o puntuación sin letras significativas
            alpha_chars = re.findall(r'[a-zA-ZáéíóúÁÉÍÓÚñÑ]', stripped)
            if len(alpha_chars) < 3 and len(stripped) > 5:
                # Si tiene pocas letras y es relativamente larga, probablemente es basura
                continue

            # 3. Líneas que son solo caracteres especiales o símbolos sueltos
            if re.match(r'^[\W_]+$', stripped) and len(stripped) > 2:
                continue

            filtered.append(line)

        return '\n'.join(filtered)


# Instancia por defecto para uso rápido
default_normalizer = TextNormalizer()