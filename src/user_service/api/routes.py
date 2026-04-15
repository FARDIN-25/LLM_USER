from fastapi import APIRouter
from . import schemas

router = APIRouter()

@router.get("/me", response_model=schemas.UserOut)
def get_me():
    # TODO: Implement get current user
    pass

@router.put("/me", response_model=schemas.UserOut)
def update_me():
    # TODO: Implement update current user
    pass
