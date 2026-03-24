from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, LoginResponse, SignupRequest, UserResponse
from app.services.auth_service import create_access_token, hash_password, verify_password

router = APIRouter()

_ALLOWED_SIGNUP_ROLES = {"developer", "pm"}


@router.post("/api/auth/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Session = Depends(get_db)) -> User:
    if body.role == "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot sign up as admin")

    if body.role not in _ALLOWED_SIGNUP_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Role must be one of {_ALLOWED_SIGNUP_ROLES}")

    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=body.email,
        name=body.name,
        role=UserRole(body.role),
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/api/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter(User.email == body.email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(user.id, user.role.value)
    return LoginResponse(access_token=token, role=user.role.value)


@router.get("/api/users/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


class _UpdateMeBody:
    def __init__(self, name: str):
        self.name = name


from pydantic import BaseModel


class UpdateMeRequest(BaseModel):
    name: str


@router.put("/api/users/me", response_model=UserResponse)
def update_me(
    body: UpdateMeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    current_user.name = body.name
    db.commit()
    db.refresh(current_user)
    return current_user
