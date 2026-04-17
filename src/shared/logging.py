import logging
from logging.handlers import TimedRotatingFileHandler
import json
import os
from datetime import datetime, timezone
from src.shared.config import settings

# Aseguramos que el directorio de logs exista
LOGS_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "message": record.getMessage(),
        }
        
        # Inyectar IDs si vienen en el diccionario 'extra'
        if hasattr(record, 'doc_id'):
            log_record['doc_id'] = record.doc_id
        if hasattr(record, 'collection_id'):
            log_record['collection_id'] = record.collection_id
            
        if record.exc_info:
            log_record["traceback"] = self.formatException(record.exc_info)
            
        return json.dumps(log_record)

def get_logger(name: str = "nexa_core"):
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        level = logging.DEBUG if settings.LOG_LEVEL == "DEBUG" else logging.INFO
        logger.setLevel(level)
        formatter = JSONFormatter()

        # 1. Salida por consola (Para ver en tiempo real)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 2. Logs Normales (Rotación diaria, retención 7 días)
        info_file = os.path.join(LOGS_DIR, "app.log")
        # when="D" (Días), interval=1 (Cada 1 día), backupCount=7 (Guarda los últimos 7)
        info_handler = TimedRotatingFileHandler(info_file, when="D", interval=1, backupCount=7)
        info_handler.setLevel(logging.INFO)
        info_handler.setFormatter(formatter)
        logger.addHandler(info_handler)

        # 3. Logs de Errores (Permanentes, solo atrapan ERROR o superior)
        error_file = os.path.join(LOGS_DIR, "error.log")
        error_handler = logging.FileHandler(error_file)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)
        
    return logger