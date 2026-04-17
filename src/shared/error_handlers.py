from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from src.shared.exceptions import NexaException
from src.shared.logging import get_logger

logger = get_logger("error_handlers")

def setup_exception_handlers(app: FastAPI):
    
    @app.exception_handler(NexaException)
    async def nexa_exception_handler(request: Request, exc: NexaException):
        logger.warning(f"Domain Error: {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            # ESTRUCTURA EXACTA QUE PEDISTE
            content={"error": True, "codigo": exc.code, "message": exc.message}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning("Payload Validation Error", extra={"details": exc.errors()})
        return JSONResponse(
            status_code=422,
            content={"error": True, "codigo": "UNPROCESSABLE_ENTITY", "message": "Datos de entrada inválidos. Revisa los campos enviados."}
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled Server Error: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": True, "codigo": "SYSTEM_FAILURE", "message": "Ocurrió un error interno en el servidor."}
        )