from bson import ObjectId
from fastapi import Depends, HTTPException, status
from app.api.setup_db import get_db
from app.db.schemas.user import Role, Permission, User
from app.api.authn import get_current_user

import logging

logger = logging.getLogger(__name__)


class RoleGuard:
    """Guard to check if the user has the required (admin, user) role."""

    def __init__(self, required_role: Role):
        self.required_role = required_role
        self.role_mapping = {
            Role.user: 1,
            Role.admin: 2,
        }

    def __call__(self, user: User = Depends(get_current_user)):
        logger.info(
            f"Checking role: user role={user.role}, required role={self.required_role}"
        )
        if self.role_mapping[user.role] >= self.role_mapping[self.required_role]:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role privileges",
        )


class GroupGuard:
    """Guard to check if the user is a member of a required group."""

    def __init__(self, required_permission: Permission):
        self.required_permission = required_permission
        self.permission_mapping = {
            Permission.read: 1,
            Permission.write: 2,
            Permission.manage: 3,
        }

    def __call__(self, group_id: str, user: User = Depends(get_current_user)):
        for perm in user.permissions:
            if str(perm.group_id) == group_id:
                if (
                    self.permission_mapping[perm.permission]
                    >= self.permission_mapping[self.required_permission]
                ):
                    return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient group permissions",
        )


async def from_title_id(title_id: str, db=Depends(get_db)):
    """Group id provider: Fetch group ID from title ID."""
    title = await db.titles.find_one({"_id": ObjectId(title_id)})
    if not title:
        raise HTTPException(404, "Title not found")
    return str(title.get("group_id"))


async def from_group_id(group_id: str):
    """Group id provider: Pass through group ID."""
    return group_id


def require_group_permission(
    required_permission: Permission,
    group_id_provider,
):
    """Dependency to check if user belongs to a group and has sufficient permissions.
    Args:
        required_permission (Permission): The required permission level.
        group_id_provider: A dependency that provides the group ID.

    Returns:
        A dependency that raises HTTPException if the user lacks permission.
    """
    guard = GroupGuard(required_permission)

    async def dep(
        group_id: str = Depends(group_id_provider),
        user: User = Depends(get_current_user),
    ) -> User:
        return guard(group_id=group_id, user=user)

    return dep


def require_role(required_role: Role):
    """Dependency to check if user has the required role.
    Args:
        required_role (Role): The required role (e.g., Role.admin).

    Returns:
        A dependency that raises HTTPException if the user lacks the required role.
    """
    guard = RoleGuard(required_role)

    async def dep(
        user: User = Depends(get_current_user),
    ) -> User:
        return guard(user=user)

    return dep
