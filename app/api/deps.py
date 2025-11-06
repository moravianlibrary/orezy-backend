import secrets
import certifi
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic_settings import BaseSettings
from pymongo import AsyncMongoClient
from contextlib import asynccontextmanager
import os


class Settings(BaseSettings):
    mongodb_uri: str = os.getenv("MONGODB_URI")
    mongodb_db: str = os.getenv("MONGODB_DB")


settings = Settings()
client: AsyncMongoClient | None = None
bearer = HTTPBearer(auto_error=False)


def require_token(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    """Dependency to require a valid bearer token for authentication."""
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


@asynccontextmanager
async def lifespan(app):
    global client
    client = AsyncMongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=5000,
        uuidRepresentation="standard",
        tlsCAFile=certifi.where(),
    )
    await client.admin.command("ping")

    db = get_db()
    # Create unique index for external_id
    await db.titles.create_index(
        [("external_id", 1)],
        unique=True,
        name="unique_external_id",
        partialFilterExpression={"external_id": {"$type": "string"}},
    )

    yield
    await client.close()


def get_db():
    assert client is not None, "DB client not initialized"
    db = client.get_database(settings.mongodb_db)
    return db
