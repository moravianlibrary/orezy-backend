from datetime import datetime, timedelta, timezone
import secrets
import string
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from jwt.exceptions import InvalidTokenError
from app.api.deps import get_db
from app.api.deps import password_hash, oauth2_scheme, settings
from pydantic import BaseModel

from app.db.schemas.user import User


class Token(BaseModel):
    access_token: str
    token_type: str


def verify_password(plain_password, hashed_password):
    """Verify a plain password against its hashed version."""
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Get the hashed version of a password."""
    return password_hash.hash(password)


def generate_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

async def authenticate_user(db, email: str, password: str):
    """Authenticate a user by their email and password."""
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(password, user["password"]):
        return False
    return user


def create_access_token(
    data: dict, expires_delta: timedelta = settings.pwd_access_token_expire_minutes
):
    """Create a JWT access token."""
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.pwd_secret_key, algorithm=settings.pwd_algorithm
    )
    return encoded_jwt


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db=Depends(get_db)
):
    """Retrieve the current user based on the provided JWT token."""
    try:
        payload = jwt.decode(
            token, settings.pwd_secret_key, algorithms=[settings.pwd_algorithm]
        )
        email = payload.get("sub")
        user = await db.users.find_one({"email": email})
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return User(**user)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
