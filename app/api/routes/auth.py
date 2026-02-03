from datetime import timedelta

from fastapi import APIRouter
from app.api.authn import Token, create_access_token
from app.deps import settings_api
from typing import Annotated
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from app.api.setup_db import get_db
from app.api.authn import (
    authenticate_user,
)
from app.api.limiter import limiter


router = APIRouter(prefix="/auth", tags=["Authentication"])

@limiter.limit("10/minute;20/hour")
@router.post("/login")
async def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db=Depends(get_db),
) -> Token:
    """Login to obtain an access token."""
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(
        minutes=settings_api.pwd_access_token_expire_minutes
    )
    access_token = create_access_token(
        data={
            "type": "user",
            "sub": user["email"],
            "role": user["role"],
        },
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")