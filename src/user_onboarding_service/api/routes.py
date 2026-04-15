from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db_service.database import get_db
from src.shared.security import get_current_user_from_cookie
from src.auth_service.infrastructure.models import UserModel
from src.user_onboarding_service.schemas import ConsentRequest, ConsentResponse, ProfessionRequest
from src.user_onboarding_service.service import (
    save_user_consent,
    save_user_details,
    save_user_interests,
    save_user_profession,
)

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


@router.post("/consent", response_model=ConsentResponse)
def save_consent(
    request: ConsentRequest,
    db: Session = Depends(get_db),
    user_email: str | None = Depends(get_current_user_from_cookie),
):
    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(UserModel).filter(UserModel.email == user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = save_user_consent(db, user.id, request.consent)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "Consent saved successfully"}

import os

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
templates = Jinja2Templates(
    directory=os.path.join(BASE_DIR, "user_onboarding_service", "templates")
)


@router.get("/welcome", response_class=HTMLResponse)
def get_welcome_page(
    request: Request,
    db: Session = Depends(get_db),
    user_email: str | None = Depends(get_current_user_from_cookie),
):
    if not user_email:
        return RedirectResponse(url="/api/auth/login", status_code=302)

    user = db.query(UserModel).filter(UserModel.email == user_email).first()
    if not user:
        return RedirectResponse(url="/api/auth/login", status_code=302)

    # If already onboarded, send to /chat
    if user.profession:
        return RedirectResponse(url="/chat", status_code=302)

    return templates.TemplateResponse(request, "welcome.html", {"user_id": user.id})


@router.get("/user-details", response_class=HTMLResponse)
def get_user_details_page(
    request: Request,
    db: Session = Depends(get_db),
    user_email: str | None = Depends(get_current_user_from_cookie),
):
    if not user_email:
        return RedirectResponse(url="/api/auth/login", status_code=302)

    user = db.query(UserModel).filter(UserModel.email == user_email).first()
    if not user:
        return RedirectResponse(url="/api/auth/login", status_code=302)

    return templates.TemplateResponse(
        request,
        "user_details.html",
        {"user_id": user.id, "full_name": getattr(user, "full_name", "") or ""},
    )

@router.get("/interests", response_class=HTMLResponse)
def get_interests_page(
    request: Request,
    db: Session = Depends(get_db),
    user_email: str | None = Depends(get_current_user_from_cookie),
):
    if not user_email:
        return RedirectResponse(url="/api/auth/login", status_code=302)

    user_data = db.query(UserModel).filter(UserModel.email == user_email).first()
    name = getattr(user_data, "full_name", "") or "User"

    return templates.TemplateResponse(
        request,
        "interests.html",
        {
            "user_name": name,
        },
    )


@router.post("/interests")
def save_interests(
    request: dict,
    db: Session = Depends(get_db),
    user_email: str | None = Depends(get_current_user_from_cookie),
):
    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    interests = request.get("interests")

    if not interests or len(interests) != 3:
        raise HTTPException(status_code=400, detail="Select exactly 3 topics")

    user = save_user_interests(db, user_email, interests)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "Interests saved"}


@router.get("/profession", response_class=HTMLResponse)
def get_profession_page(
    request: Request,
    db: Session = Depends(get_db),
    user_email: str | None = Depends(get_current_user_from_cookie),
):
    if not user_email:
        return RedirectResponse(url="/api/auth/login", status_code=302)

    user = db.query(UserModel).filter(UserModel.email == user_email).first()
    if not user:
        return RedirectResponse(url="/api/auth/login", status_code=302)

    return templates.TemplateResponse(request, "profession.html")


@router.post("/profession")
def save_profession(
    request: ProfessionRequest,
    db: Session = Depends(get_db),
    user_email: str | None = Depends(get_current_user_from_cookie),
):
    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    profession = request.profession
    if not profession:
        raise HTTPException(status_code=400, detail="Select a profession")

    try:
        save_user_profession(db, user_email, profession)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "Profession saved"}


@router.post("/user-details")
def save_details(
    request: dict,
    db: Session = Depends(get_db),
    user_email: str | None = Depends(get_current_user_from_cookie),
):
    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(UserModel).filter(UserModel.email == user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    full_name = request.get("full_name")
    user = save_user_details(db, user.id, full_name)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User details saved"}
