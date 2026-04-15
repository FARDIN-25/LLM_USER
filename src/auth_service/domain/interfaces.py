from abc import ABC, abstractmethod
from typing import Optional
from src.auth_service.domain.entities import User

class AuthRepositoryInterface(ABC):
    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    def create(self, user: User) -> User:
        pass
