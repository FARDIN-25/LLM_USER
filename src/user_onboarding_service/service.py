from sqlalchemy.orm import Session

from src.auth_service.infrastructure.models import UserModel


def save_user_consent(db: Session, user_id: int, consent: bool):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()

    if not user:
        return None

    # Guard: if model/db column isn't present yet, don't crash the request.
    if hasattr(user, "consent_for_training"):
        user.consent_for_training = consent
    db.commit()
    db.refresh(user)

    return user


def save_user_details(db: Session, user_id: int, full_name: str):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()

    if not user:
        return None

    user.full_name = full_name
    db.commit()
    db.refresh(user)

    return user


def save_user_interests(db: Session, user_email: str, interests):
    user = db.query(UserModel).filter(UserModel.email == user_email).first()

    if not user:
        return None

    user.interests = interests
    db.commit()
    db.refresh(user)

    return user


def save_user_profession(db: Session, user_email: str, profession: str):
    user = db.query(UserModel).filter(UserModel.email == user_email).first()

    if not user:
        raise ValueError("User not found")

    user.profession = profession
    db.commit()
    db.refresh(user)

    return user

