import certifi
from fastapi.security import HTTPBearer, OAuth2PasswordBearer
from app.db.operations.api import add_users_to_group_bulk
from app.db.schemas.group import Group
from app.db.schemas.user import Maintains, Permission, User
from pymongo import AsyncMongoClient
from contextlib import asynccontextmanager
import os
from pwdlib import PasswordHash
from app.deps import settings_db

from app.db.schemas.user import Role



client: AsyncMongoClient | None = None
bearer = HTTPBearer(auto_error=False) # for static token auth of NDK endpoints
password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login") # for user auth via JWT tokens


@asynccontextmanager
async def lifespan(app):
    global client

    client_kwargs = {
        "serverSelectionTimeoutMS": 5000,
        "uuidRepresentation": "standard",
    }
    if settings_db.tls_enabled:
        client_kwargs["tlsCAFile"] = certifi.where()

    client = AsyncMongoClient(settings_db.mongodb_uri, **client_kwargs)
    await client.admin.command("ping")

    db = get_db()
    await create_indexes(db)
    await create_admin(db)
    if os.getenv("NDK_DEPLOYMENT", "false").lower() in ("1", "true", "yes"):
        await create_ndk_group(db)

    yield
    await client.close()


def get_db():
    assert client is not None, "DB client not initialized"
    db = client.get_database(settings_db.mongodb_db)
    return db


async def create_ndk_group(db):
    """Create a default NDK group if none exists."""
    existing_group = await db.groups.find_one({"name": "NDK"})
    if existing_group:
        return

    group = Group(
        name="NDK",
        description="Skupina pro tituly z NDK linky",
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
        [("name", 1)], unique=True, name="unique_group_name"
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
        full_name=os.getenv("ADMIN_NAME"),
        email=os.getenv("ADMIN_EMAIL"),
        password=os.getenv("ADMIN_PASSWORD"),
        role=Role.admin,
        permissions=permissions,
    )
    user = user.model_dump(by_alias=True)
    user["password"] = password_hash.hash(user["password"])

    await db.users.insert_one(user)
