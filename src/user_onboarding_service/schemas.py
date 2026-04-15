from pydantic import BaseModel


class ConsentRequest(BaseModel):
    consent: bool


class ConsentResponse(BaseModel):
    message: str


class ProfessionRequest(BaseModel):
    profession: str


class ProfessionRequest(BaseModel):
    profession: str