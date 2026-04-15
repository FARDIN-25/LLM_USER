from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("rag_enterprise")

class BaseAppException(Exception):
    """Base class for application exceptions."""
    def __init__(
        self, 
        message: str, 
        status_code: int = 500, 
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class DomainException(BaseAppException):
    """Exception raised for domain logic errors."""
    def __init__(self, message: str, error_code: str = "DOMAIN_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, error_code=error_code, details=details)

class NotFoundException(BaseAppException):
    """Exception raised when a resource is not found."""
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=404, error_code="NOT_FOUND", details=details)

class UnauthorizedException(BaseAppException):
    """Exception raised for authentication errors."""
    def __init__(self, message: str = "Unauthorized", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=401, error_code="UNAUTHORIZED", details=details)

class InfrastructureException(BaseAppException):
    """Exception raised for infrastructure errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=503, error_code="INFRASTRUCTURE_ERROR", details=details)

async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for all unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred.",
                "type": exc.__class__.__name__
            }
        }
    )

async def app_exception_handler(request: Request, exc: BaseAppException):
    """Handler for application-specific exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )
