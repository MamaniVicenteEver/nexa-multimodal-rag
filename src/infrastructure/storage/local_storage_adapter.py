import os
import aiofiles
from src.core.ports.file_storage import IFileStorage
from src.shared.config import settings

class LocalStorageAdapter(IFileStorage):
    def __init__(self):
        # Usamos una ruta relativa a la raíz del proyecto
        self.storage_path = os.path.join(os.getcwd(), "data", "storage")
        os.makedirs(self.storage_path, exist_ok=True)

    async def save_file(self, file_bytes: bytes, filename: str) -> str:
        file_path = os.path.join(self.storage_path, filename)
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_bytes)
            
        return file_path