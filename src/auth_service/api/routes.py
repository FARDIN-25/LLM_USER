from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os

from src.db_service.database import get_db
from src.auth_service.api.schemas import UserCreate, UserLogin, UserOut, Token
from src.auth_service.infrastructure.repositories import AuthRepository
from src.auth_service.application.services import AuthService
from src.auth_service.infrastructure.models import UserModel

router = APIRouter()

# Setup templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    repository = AuthRepository(db)
    return AuthService(repository)

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")

@router.post("/register", response_model=UserOut)
async def register(
    request: Request,
    user_data: UserCreate, 
    service: AuthService = Depends(get_auth_service)
):
    try:
        user = service.register_user(user_data)
        # If this endpoint is ever hit by a browser form submit, redirect to consent.
        content_type = (request.headers.get("content-type") or "").lower()
        if not content_type.startswith("application/json"):
            return RedirectResponse(url="/onboarding/welcome", status_code=302)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    user_data: UserLogin, 
    db: Session = Depends(get_db),
    service: AuthService = Depends(get_auth_service)
):
    token = service.login_user(user_data)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Set cookie for UI access
    response.set_cookie(
        key="access_token",
        value=token.access_token,
        httponly=True,
        max_age=1800, # 30 min match with token expiry
        expires=1800,
        path="/",
        samesite="lax",
        secure=False,
    )

    # Consent gate:
    # If user never gave consent (NULL), force welcome page on login.
    user = db.query(UserModel).filter(UserModel.email == user_data.email).first()
    consent_value = getattr(user, "consent_for_training", None) if user else None
    redirect_to = "/onboarding/welcome" if consent_value is None else "/chat"

    # Browser form-submit (non-JSON) should redirect directly.
    content_type = (request.headers.get("content-type") or "").lower()
    if not content_type.startswith("application/json"):
        redirect = RedirectResponse(url=redirect_to, status_code=302)
        redirect.set_cookie(
            key="access_token",
            value=token.access_token,
            httponly=True,
            max_age=1800,
            expires=1800,
            path="/",
            samesite="lax",
            secure=False,
        )
        return redirect

    # Fetch/XHR callers keep JSON, but get the next location.
    return {"access_token": token.access_token, "token_type": token.token_type, "redirect_to": redirect_to}
