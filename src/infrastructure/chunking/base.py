"""
Funciones base compartidas por los chunkers.
"""

import re
from typing import List


def clean_whitespace(text: str) -> str:
    """Normaliza espacios en blanco sin destruir formato Markdown."""
    # Reemplazar múltiples espacios por uno solo (excepto saltos de línea)
    text = re.sub(r'[ \t]+', ' ', text)
    # Eliminar espacios al final de cada línea
    text = re.sub(r' +$', '', text, flags=re.MULTILINE)
    return text.strip()


def merge_small_chunks(chunks: List[str], min_size: int = 100) -> List[str]:
    """Fusiona chunks demasiado pequeños con el siguiente."""
    if not chunks:
        return []
    merged = []
    buffer = ""
    for chunk in chunks:
        if len(buffer) < min_size:
            buffer += " " + chunk if buffer else chunk
        else:
            if buffer:
                merged.append(buffer)
            buffer = chunk
    if buffer:
        merged.append(buffer)
    # Si el último es muy pequeño, fusionar con el anterior
    if len(merged) >= 2 and len(merged[-1]) < min_size:
        merged[-2] = merged[-2] + " " + merged[-1]
        merged.pop()
    return merged