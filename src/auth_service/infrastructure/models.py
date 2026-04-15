from sqlalchemy import Column, Integer, String, Boolean, JSON
from src.db_service.database import Base


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    consent_for_training = Column(Boolean, nullable=True)
    interests = Column(JSON, nullable=True)
    profession = Column(String, nullable=True)  # ✅ correct