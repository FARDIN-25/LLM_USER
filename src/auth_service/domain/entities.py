from pydantic import BaseModel, EmailStr
from typing import Optional

class User(BaseModel):
    id: Optional[int] = None
    email: EmailStr
    hashed_password: str
    is_active: bool = True
    is_superuser: bool = False
