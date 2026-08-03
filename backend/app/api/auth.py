from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..config import settings
from ..deps import CurrentUser, Db
from ..models import Cohort, User
from ..schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut, UserUpdate
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _token(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: Db) -> TokenResponse:
    existing = (
        await db.execute(select(User).where(User.email == body.email.lower()))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email exists")

    cohort_id = None
    if body.cohort_code:
        cohort = (
            await db.execute(select(Cohort).where(Cohort.name == body.cohort_code))
        ).scalar_one_or_none()
        if cohort is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown cohort code")
        cohort_id = cohort.id

    user = User(
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        name=body.name or "Analyst",
        cohort_id=cohort_id,
    )
    db.add(user)
    await db.flush()
    return _token(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: Db) -> TokenResponse:
    user = (
        await db.execute(select(User).where(User.email == body.email.lower()))
    ).scalar_one_or_none()
    # Same message either way -- do not disclose which accounts exist.
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return _token(user)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(body: UserUpdate, user: CurrentUser, db: Db) -> User:
    if body.name is not None:
        user.name = body.name
    if body.photo_url is not None:
        user.photo_url = body.photo_url
    db.add(user)
    return user
