import certifi
from fastapi.security import HTTPBearer, OAuth2PasswordBearer
from app.db.operations.api import add_users_to_group_bulk
from app.db.schemas.group import Group
from app.db.schemas.user import Maintains, Permission, User
from pydantic_settings import BaseSettings
from pymongo import AsyncMongoClient
from contextlib import asynccontextmanager
import os
from pwdlib import PasswordHash

from app.db.schemas.user import Role


class Settings(BaseSettings):
    mongodb_uri: str = os.getenv("MONGODB_URI")
    mongodb_db: str = os.getenv("MONGODB_DB")
    tls_enabled: bool = os.getenv("ENABLE_TLS", "false").lower() in ("1", "true", "yes")
    pwd_secret_key: str = os.getenv("PWD_SECRET")
    pwd_algorithm: str = os.getenv("PWD_ALGORITHM", "HS256")
    pwd_access_token_expire_minutes: int = int(
        os.getenv("PASSWD_ACCESS_TOKEN_EXPIRE_MINUTES", "10080")
    )


settings = Settings()
client: AsyncMongoClient | None = None
bearer = HTTPBearer(auto_error=False)
password_hash = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")
require_token = oauth2_scheme


@asynccontextmanager
async def lifespan(app):
    global client

    client_kwargs = {
        "serverSelectionTimeoutMS": 5000,
        "uuidRepresentation": "standard",
    }
    if settings.tls_enabled:
        client_kwargs["tlsCAFile"] = certifi.where()

    client = AsyncMongoClient(settings.mongodb_uri, **client_kwargs)
    await client.admin.command("ping")

    db = get_db()
    await create_indexes(db)
    await create_admin(db)
    await create_default_group(db)

    yield
    await client.close()


def get_db():
    assert client is not None, "DB client not initialized"
    db = client.get_database(settings.mongodb_db)
    return db


async def create_default_group(db):
    """Create a default group if none exists."""
    existing_group = await db.groups.find_one({"short_name": "DEF"})
    if existing_group:
        return

    group = Group(
        short_name="DEF",
        full_name="Default Group",
        description="Default group for new titles and users.",
    ).model_dump(by_alias=True)
    await db.groups.insert_one(group)

    # Add admins to default group
    admin_users = await db.users.find({"role": Role.admin.value}).to_list(length=None)
    await add_users_to_group_bulk(
        group_id=group["_id"],
        user_ids=[user["_id"] for user in admin_users],
        permission=Permission.manage,
        db=db,
    )


async def create_indexes(db):
    """Create necessary indexes in the database."""
    await db.titles.create_index(
        [("external_id", 1)],
        unique=True,
        name="unique_external_id",
        partialFilterExpression={"external_id": {"$type": "string"}},
    )
    await db.groups.create_index(
        [("short_name", 1)], unique=True, name="unique_group_short_name"
    )
    await db.users.create_index([("email", 1)], unique=True, name="unique_user_email")
    await db.users.create_index([("role", 1)], name="role_index")


async def create_admin(db):
    """Create an admin user if none exists.
    Uses ADMIN_EMAIL and ADMIN_PASSWORD env vars.
    Has all group permissions.
    """
    existing_admin = await db.users.find_one({"role": "admin"})
    if existing_admin:
        return

    group_ids = await db.groups.distinct("_id")
    permissions = []
    for group_id in group_ids:
        permissions.append(Maintains(group_id=group_id, permission=Permission.manage))

    user = User(
        full_name="Main Administrator",
        email=os.getenv("ADMIN_EMAIL"),
        password=os.getenv("ADMIN_PASSWORD"),
        role=Role.admin,
        permissions=permissions,
    )
    user = user.model_dump(by_alias=True)
    user["password"] = password_hash.hash(user["password"])

    await db.users.insert_one(user)
