from datetime import datetime, timedelta, timezone
import os
import secrets
import string
from typing import Annotated

from fastapi.security import HTTPAuthorizationCredentials
import jwt
from fastapi import Depends, HTTPException, status
from app.api.setup_db import get_db
from app.api.setup_db import password_hash, oauth2_scheme, bearer
from app.deps import settings_api
from pydantic import BaseModel

from app.db.schemas.user import User

class Token(BaseModel):
    access_token: str
    token_type: str


def require_token(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    """Dependency to require a valid bearer token for static authentication (NDK)."""
    if credentials is None or not credentials.scheme.lower() == "bearer":
        # Force browsers/clients to prompt correctly:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials

    if not secrets.compare_digest(token, os.getenv("WEBAPP_TOKEN")):
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"token": token}


def verify_password(plain_password, hashed_password):
    """Verify a plain password against its hashed version.

    Args:
        plain_password (str): The plain text password to verify.
        hashed_password (str): The hashed password to compare against.
    Returns:
        bool: password match.
    """
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Get the hashed version of a password.

    Args:
        password (str): The plain text password to hash.
    Returns:
        str: hashed password.
    """
    return password_hash.hash(password)


def generate_password(length: int = 16) -> str:
    """Generate a secure random password.

    Args:
        length (int): Length of the generated password. Default is 16.
    Returns:
        str: The generated password.
    """
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def authenticate_user(db, email: str, password: str) -> User | bool:
    """Authenticate a user by their email and password.

    Args:
        db: Database connection.
        email (str): The user's email.
        password (str): The user's plain text password.
    Returns:
        User | bool: The authenticated user object if successful, False otherwise."""
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(password, user["password"]):
        return False
    return user


def create_access_token(
    data: dict, expires_delta: timedelta = settings_api.pwd_access_token_expire_minutes
):
    """Create a JWT access token.

    Args:
        data (dict): The data to encode in the token.
        expires_delta (timedelta): The token's expiration time.
    Returns:
        str: The encoded JWT token.
    """
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings_api.pwd_secret_key, algorithm=settings_api.pwd_algorithm
    )
    return encoded_jwt


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db=Depends(get_db)
):
    """Retrieve the current user based on the provided JWT token.

    Args:
        token (str): The JWT token from the request.
        db: Database connection.
    Returns:
        User: The current authenticated user.
    Raises:
        HTTPException: If the token is invalid or the user cannot be found.
    """
    try:
        payload = jwt.decode(
            token, settings_api.pwd_secret_key, algorithms=[settings_api.pwd_algorithm]
        )
        email = payload.get("sub")
        user = await db.users.find_one({"email": email})
        return User(**user)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
