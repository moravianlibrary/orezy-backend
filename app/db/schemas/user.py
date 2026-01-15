from datetime import datetime
from enum import Enum
import re
import secrets
import string

from pydantic import BaseModel, Field, field_validator

from app.db.schemas.base import BaseModelWithId


class Role(str, Enum):
    user = "user"
    admin = "admin"


class Permission(str, Enum):
    read = "read"
    write = "write"
    manage = "manage"


class Maintains(BaseModel):
    group_id: str
    permission: Permission
    created_at: datetime = Field(default_factory=datetime.now)


class User(BaseModelWithId):
    email: str
    full_name: str
    role: Role = Role.user
    permissions: list[Maintains] = Field(default_factory=list)
    password: str = ""

    @field_validator("email")
    def validate_email(cls, v: str) -> str:
        pattern = r"^[^@]+@[^@]+\.[^@]+$"
        if not re.match(pattern, v or ""):
            raise ValueError("Invalid email address")
        return v.lower()

class UserCreate(BaseModel):
    email: str
    full_name: str
    role: Role = Role.user
    permissions: list[Maintains] = Field(default_factory=list)


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    permissions: list[Maintains] | None = None
