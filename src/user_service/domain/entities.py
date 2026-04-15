from pydantic import BaseModel
from typing import Optional

class UserProfile(BaseModel):
    user_id: str
    full_name: Optional[str] = None
    role: str = "user"
