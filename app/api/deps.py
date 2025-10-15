import certifi
from pydantic_settings import BaseSettings
from pymongo import AsyncMongoClient
from contextlib import asynccontextmanager
import os


class Settings(BaseSettings):
    mongodb_uri: str = os.getenv("MONGODB_URI")
    mongodb_db: str = os.getenv("MONGODB_DB")


settings = Settings()
client: AsyncMongoClient | None = None


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
