from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User, UserRole

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_access_token(user_id: int, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        # No "exp" — token never expires, user must click logout
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},  # No expiration check
        )
    except JWTError:
        return None


def seed_admin(db: Session) -> None:
    """Create the admin user from settings if it does not already exist."""
    existing = db.query(User).filter(User.email == settings.admin_email).first()
    if existing:
        return
    admin = User(
        email=settings.admin_email,
        name="Admin",
        role=UserRole.admin,
        password_hash=hash_password(settings.admin_password),
    )
    db.add(admin)
    db.commit()
