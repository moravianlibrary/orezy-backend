from pydantic_settings import BaseSettings
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from contextlib import asynccontextmanager
import os


class Settings(BaseSettings):
    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_db: str = os.getenv("MONGODB_DB", "myapp")


settings = Settings()

client: AsyncIOMotorClient | None = None
db: AsyncIOMotorDatabase | None = None


async def ensure_indexes(database: AsyncIOMotorDatabase) -> None:
    # await database.users.create_index([("email", ASCENDING)], unique=True)
    pass


@asynccontextmanager
async def lifespan(app):
    global client, db
    client = AsyncIOMotorClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=5000,
        uuidRepresentation="standard",
    )
    db = client[settings.mongodb_db]
    await ensure_indexes(db)
    yield
    client.close()


def get_db() -> AsyncIOMotorDatabase:
    assert db is not None, "DB not initialized"
    return db
