from datetime import datetime
import logging
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from app.api.limiter import limiter
from app.api.setup_db import get_db
from app.api.authz import from_group_id, require_group_permission, require_role
from app.db.operations.api import get_user_permissions_in_group, get_users_in_group
from app.db.schemas.group import APIkey, Group, GroupCreate, GroupUpdate
from app.db.schemas.user import Maintains, Permission, Role, User
from app.api.authn import (
    get_current_user,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/groups", tags=["Groups"])


@limiter.limit("60/minute;600/hour")
@router.get("")
async def list_groups(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db=Depends(get_db),
):
    """Lists all groups user belongs to."""
    group_read_permission_ids = [ObjectId(perm.group_id)
        for perm in current_user.permissions
        if Permission.read_group in perm.permission
    ]
    groups = await db.groups.find({"_id": {"$in": group_read_permission_ids}}).to_list(length=None)
    for group in groups:
        # Display permissions inside every group
        group["permissions"] = await get_user_permissions_in_group(
            current_user, ObjectId(group["_id"])
        )
        # Admin user can also see list of users and api_key
        if current_user.role == Role.admin:
            group["users"] = await get_users_in_group(ObjectId(group["_id"]), db)
        else:
            group.pop("api_key", None)

        # Replace title_ids with title_count
        group["title_count"] = len(group["title_ids"])
        group.pop("title_ids", None)

    return jsonable_encoder(groups, custom_encoder={ObjectId: str})


@limiter.limit("2000/minute")
@router.get(
    "/{group_id}",
    dependencies=[
        Depends(
            require_group_permission(Permission.read_group, group_id_provider=from_group_id)
        )
    ],
)
async def get_titles(request: Request, group_id: str, db=Depends(get_db)):
    """Gets all titles from the database.

    Returns:
        dict: Titles containing their IDs, states, creation and modification dates.
    """
    if not ObjectId.is_valid(group_id):
        raise HTTPException(400, f"ID '{group_id}' is not a valid ObjectId")

    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    titles = await db.titles.find(
        {"group_id": ObjectId(group_id)},
        {"_id": 1, "state": 1, "created_at": 1, "modified_at": 1},
    ).to_list(None)

    # Show most recently created titles first
    titles = sorted(titles, key=lambda x: x["created_at"], reverse=True)

    group["titles"] = titles
    return jsonable_encoder(
        group, custom_encoder={ObjectId: str}, exclude=["title_ids", "api_key"]
    )


@limiter.limit("60/minute;600/hour")
@router.post("", dependencies=[Depends(require_role(Role.admin))])
async def create_group(
    request: Request,
    group: GroupCreate,
    db=Depends(get_db),
):
    """Creates a new group."""
    group = Group(**group.model_dump()).model_dump(by_alias=True)
    result = await db.groups.insert_one(group)

    # Add admins to group
    admin_users = await db.users.find({"role": Role.admin.value}).to_list(length=None)
    new_permission = Maintains(
        group_id=str(result.inserted_id), permission=list(Permission)
    ).model_dump()
    await db.users.update_many(
        {"_id": {"$in": [user["_id"] for user in admin_users]}},
        {"$push": {"permissions": new_permission}},
    )

    return {"id": str(result.inserted_id), "api_key": group["api_key"]["key"]}


@limiter.limit("60/minute;600/hour")
@router.post(
    "/{group_id}/members/{user_id}", dependencies=[Depends(require_role(Role.admin))]
)
async def add_group_member(
    request: Request,
    group_id: str,
    user_id: str,
    permission: list[Permission],
    db=Depends(get_db),
):
    """Updates group members and their permissions."""
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    new_permission = Maintains(group_id=group_id, permission=permission).model_dump()
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$push": {"permissions": new_permission}},
    )

    return {"detail": "Group member added"}


@limiter.limit("60/minute;600/hour")
@router.patch(
    "/{group_id}/members/{user_id}", dependencies=[Depends(require_role(Role.admin))]
)
async def update_group_member(
    request: Request,
    group_id: str,
    user_id: str,
    permission: list[Permission],
    db=Depends(get_db),
):
    """Updates group members and their permissions."""
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    user_permission = await db.users.find_one(
        {"_id": ObjectId(user_id), "permissions.group_id": ObjectId(group_id)},
        {"permissions.$": 1},
    )
    if not user_permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of the group",
        )
    await db.users.update_one(
        {"_id": ObjectId(user_id), "permissions.group_id": ObjectId(group_id)},
        {"$set": {"permissions.$.permission": permission}},
    )

    return {"detail": "Group member updated"}


@limiter.limit("60/minute;600/hour")
@router.delete(
    "/{group_id}/members/{user_id}", dependencies=[Depends(require_role(Role.admin))]
)
async def remove_group_member(
    request: Request,
    group_id: str,
    user_id: str,
    db=Depends(get_db),
):
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    # Prevent removing admin users
    admin_user_ids = await db.users.find({"role": Role.admin.value}).to_list(
        length=None
    )
    admin_user_ids = [user["_id"] for user in admin_user_ids]
    if ObjectId(user_id) in admin_user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove admin users from group",
        )

    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$pull": {"permissions": {"group_id": ObjectId(group_id)}}},
    )

    return {"detail": "Group member removed"}


@limiter.limit("60/minute;600/hour")
@router.patch("/{group_id}", dependencies=[Depends(require_role(Role.admin))])
async def update_group(
    request: Request,
    group_id: str,
    group: GroupUpdate,
    db=Depends(get_db),
):
    """Updates group details."""
    existing_group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not existing_group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    update_data = {k: v for k, v in group.model_dump().items() if v is not None}
    update_data["modified_at"] = datetime.now()
    if update_data:
        await db.groups.update_one(
            {"_id": ObjectId(group_id)},
            {"$set": update_data},
        )

    return {"detail": "Group updated"}


@limiter.limit("60/minute;600/hour")
@router.delete("/{group_id}", dependencies=[Depends(require_role(Role.admin))])
async def delete_group(request: Request, group_id: str, db=Depends(get_db)):
    """Deletes a group and its titles (!!)"""
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    # Delete group
    await db.groups.delete_one({"_id": ObjectId(group_id)})

    # Remove from users
    group_permissions = await db.users.distinct("permissions", {"group_ids": group_id})
    await db.users.update_many(
        {"_id": {"$in": group_permissions}},
        {"$pull": {"permissions": {"group_id": group_id}}},
    )
    # Cascade - Remove titles in the group
    await db.titles.delete_many({"group_id": group_id})

    return {"detail": "Group deleted"}


@limiter.limit("1/minute")
@router.post(
    "/{group_id}/api-key",
    dependencies=[Depends(require_role(Role.admin))],
)
async def revoke_group_api_key(
    request: Request,
    group_id: str,
    db=Depends(get_db),
):
    """Revoke API key for the group and create a new one."""
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    new_api_key = APIkey()
    await db.groups.update_one(
        {"_id": ObjectId(group_id)},
        {"$set": {"api_key": new_api_key.model_dump(by_alias=True)}},
    )

    return jsonable_encoder(new_api_key, custom_encoder={ObjectId: str})
