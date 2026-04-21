from enum import Enum

class CollectionType(str, Enum):
    """
    Tipos de colección soportados por el sistema.
    Determina cómo se procesan y recuperan los documentos.
    """
    CATALOG = "catalog"    # Productos, entidades discretas
    DOCUMENT = "document"  # Informes, manuales, textos narrativos

    @classmethod
    def from_string(cls, value: str) -> "CollectionType":
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Tipo de colección inválido: {value}. Use 'catalog' o 'document'.")