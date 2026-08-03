from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .models import Session as RunSession, User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)


async def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    user = await db.get(User, payload.get("sub"))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


async def facilitator(
    user: Annotated[User, Depends(current_user)],
) -> User:
    if user.role != "facilitator":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Facilitator access required")
    return user


async def owned_session(
    session_id: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RunSession:
    stmt = select(RunSession).where(RunSession.id == session_id)
    run = (await db.execute(stmt)).scalar_one_or_none()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if run.user_id != user.id and user.role != "facilitator":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your session")
    return run


CurrentUser = Annotated[User, Depends(current_user)]
Facilitator = Annotated[User, Depends(facilitator)]
Db = Annotated[AsyncSession, Depends(get_db)]
OwnedSession = Annotated[RunSession, Depends(owned_session)]
