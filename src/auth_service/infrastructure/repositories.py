from typing import Optional
from sqlalchemy.orm import Session
from src.auth_service.domain.interfaces import AuthRepositoryInterface
from src.auth_service.domain.entities import User
from src.auth_service.infrastructure.models import UserModel

class AuthRepository(AuthRepositoryInterface):
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> Optional[User]:
        user_model = self.db.query(UserModel).filter(UserModel.email == email).first()
        if user_model:
            return User(
                id=user_model.id,
                email=user_model.email,
                hashed_password=user_model.hashed_password,
                is_active=user_model.is_active,
                is_superuser=user_model.is_superuser
            )
        return None

    def create(self, user: User) -> User:
        user_model = UserModel(
            email=str(user.email),
            hashed_password=user.hashed_password,
            is_active=user.is_active,
            is_superuser=user.is_superuser
        )
        self.db.add(user_model)
        self.db.commit()
        self.db.refresh(user_model)
        
        return User(
            id=user_model.id,
            email=user_model.email,
            hashed_password=user_model.hashed_password,
            is_active=user_model.is_active,
            is_superuser=user_model.is_superuser
        )
