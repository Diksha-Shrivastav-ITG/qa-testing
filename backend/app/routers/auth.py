from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, LoginResponse, SignupRequest, UserResponse
from app.services.auth_service import create_access_token, hash_password, verify_password

router = APIRouter()

_ALLOWED_SIGNUP_ROLES = {"developer"}


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


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

from app.deps import require_role
from typing import Optional
from fastapi import Query


@router.get("/api/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> list[User]:
    """List all users. Admin only."""
    return db.query(User).order_by(User.id.asc()).all()


class AdminUpdateUserRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None


@router.patch("/api/users/{user_id}", response_model=UserResponse)
def admin_update_user(
    user_id: int,
    body: AdminUpdateUserRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> User:
    """Update a user's name or role. Admin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        try:
            user.role = UserRole(body.role)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role: {body.role}")

    db.commit()
    db.refresh(user)
    return user


@router.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role("admin")),
) -> None:
    """Delete a user. Admin only. Cannot delete yourself."""
    if user_id == admin_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    db.delete(user)
    db.commit()
