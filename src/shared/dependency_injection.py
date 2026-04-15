from fastapi import Depends
from sqlalchemy.orm import Session
from src.db_service.database import get_db
from src.shared.config import settings, Settings

# Generic Repository Dependency
def get_repository(repo_type: type):
    """Generic repo provider for repository pattern."""
    def _get_repo(db: Session = Depends(get_db)):
        return repo_type(db)
    return _get_repo

# Core Dependencies
def get_current_settings() -> Settings:
    """Dependency for accessing application settings."""
    return settings
