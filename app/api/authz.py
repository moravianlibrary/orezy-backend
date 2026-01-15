from bson import ObjectId
from fastapi import Depends, HTTPException, status
from app.api.deps import get_db
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


# Group id providers:
async def from_title_id(title_id: str, db=Depends(get_db)):
    title = await db.titles.find_one({"_id": ObjectId(title_id)})
    if not title:
        raise HTTPException(404, "Title not found")
    return str(title.get("group_id"))


async def from_group_id(group_id: str):
    return group_id


def require_group_permission(
    required_permission: Permission,
    group_id_provider,
):
    guard = GroupGuard(required_permission)

    async def dep(
        group_id: str = Depends(group_id_provider),
        user: User = Depends(get_current_user),
    ) -> User:
        # call your original guard logic with the resolved group_id
        return guard(group_id=group_id, user=user)

    return dep


def require_role(required_role: Role):
    guard = RoleGuard(required_role)

    async def dep(
        user: User = Depends(get_current_user),
    ) -> User:
        # call your original guard logic
        return guard(user=user)

    return dep
