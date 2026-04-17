from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List

class DocumentChunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 100):
        self.splitter = RecursiveCharacterTextSplitter(
            separators=["## ", "\n\n", "\n", ". ", " ", ""],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    def split_text(self, text: str) -> List[str]:
        return self.splitter.split_text(text)