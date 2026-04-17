class NexaException(Exception):
    """Excepción base para toda la lógica de negocio de Nexa."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)

class ValidationException(NexaException):
    def __init__(self, message: str):
        super().__init__(message, code="VALIDATION_ERROR", status_code=400)

class ExternalServiceException(NexaException):
    def __init__(self, message: str, service: str):
        super().__init__(message, code=f"{service.upper()}_ERROR", status_code=502)