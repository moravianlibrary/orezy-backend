from datetime import datetime
from enum import Enum
import re
import secrets
import string

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.schemas.base import BaseModelWithId, ObjectIdField


class Role(str, Enum):
    user = "user"
    admin = "admin"


class Permission(str, Enum):
    read = "read"
    write = "write"
    manage = "manage"


class Maintains(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    group_id: ObjectIdField
    permission: Permission
    created_at: datetime = Field(default_factory=datetime.now)


class User(BaseModelWithId):
    email: str
    full_name: str
    role: Role = Role.user
    permissions: list[Maintains] = Field(default_factory=list)
    password: str = Field(default_factory=lambda: User.create_random_password())

    @field_validator("email")
    def validate_email(cls, v: str) -> str:
        pattern = r"^[^@]+@[^@]+\.[^@]+$"
        if not re.match(pattern, v or ""):
            raise ValueError("Invalid email address")
        return v.lower()
    
    @staticmethod
    def create_random_password(length: int = 16) -> str:
        """Generate a secure random password.

        Args:
            length (int): Length of the generated password. Default is 16.
        Returns:
            str: The generated password.
        """
        alphabet = string.ascii_letters + string.digits + string.punctuation
        return "".join(secrets.choice(alphabet) for _ in range(length))


class UserCreate(BaseModel):
    email: str
    full_name: str
    role: Role = Role.user
    permissions: list[Maintains] = Field(default_factory=list)


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    permissions: list[Maintains] | None = None
