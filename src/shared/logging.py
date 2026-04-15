import logging
import sys
import json
from datetime import datetime
from src.shared.config import settings

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging in production."""
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "line": record.lineno
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def setup_logging():
    """Configure structured logging for the application."""
    handler = logging.StreamHandler(sys.stdout)
    
    if settings.is_production:
        handler.setFormatter(JSONFormatter())
    else:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        handler.setFormatter(logging.Formatter(log_format))

    logging.basicConfig(
        level=logging.INFO if not settings.DEBUG else logging.DEBUG,
        handlers=[handler],
        force=True
    )
    
    # Set levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger("rag_enterprise")
