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
from app.db.schemas.group import Group, GroupCreate, GroupUpdate
from app.db.schemas.user import Maintains, Permission, Role, User
from app.api.authn import (
    get_current_user,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/groups", tags=["groups"])


@limiter.limit("60/minute;600/hour")
@router.get("")
async def list_groups(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db=Depends(get_db),
):
    """Lists all groups user belongs to."""
    user_group_ids = [ObjectId(perm.group_id) for perm in current_user.permissions]
    groups = await db.groups.find({"_id": {"$in": user_group_ids}}).to_list(
        length=None
    )
    for group in groups:
        # join permission with groups
        group["permission"] = await get_user_permissions_in_group(
            current_user, ObjectId(group["_id"])
        )
        if group["permission"] == Permission.manage:
            group["users"] = await get_users_in_group(ObjectId(group["_id"]), db)

        # replace title_ids with title_count
        group["title_count"] = len(group["title_ids"])
        group.pop("title_ids", None)

    return jsonable_encoder(groups, custom_encoder={ObjectId: str})

@limiter.limit("2000/minute")
@router.get(
    "/{group_id}",
    dependencies=[
        Depends(
            require_group_permission(Permission.read, group_id_provider=from_group_id)
        )
    ],
)
async def get_title_ids(request: Request, group_id: str, db=Depends(get_db)):
    """Gets all title IDs from the database.

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
    return jsonable_encoder(group, custom_encoder={ObjectId: str}, exclude=["title_ids"])


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
        group_id=str(result.inserted_id), permission=Permission.manage
    ).model_dump()
    await db.users.update_many(
        {"_id": {"$in": [user["_id"] for user in admin_users]}},
        {"$push": {"permissions": new_permission}},
    )

    return {"id": str(result.inserted_id)}


@limiter.limit("60/minute;600/hour")
@router.patch("/{group_id}/add", dependencies=[Depends(require_role(Role.admin))])
async def add_group_members(
    request: Request,
    group_id: str,
    user_ids: list[str],
    permissions: list[Permission],
    db=Depends(get_db),
):
    """Updates group members and their permissions."""
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    for user_id, permission in zip(user_ids, permissions):
        new_permission = Maintains(group_id=group_id, permission=permission).model_dump()
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$push": {"permissions": new_permission}},
        )

    return {"detail": "Group members updated"}


@limiter.limit("60/minute;600/hour")
@router.patch("/{group_id}/remove", dependencies=[Depends(require_role(Role.admin))])
async def remove_group_members(
    request: Request,
    group_id: str,
    user_ids: list[str],
    db=Depends(get_db),
):
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    
    # Prevent removing admin users
    admin_user_ids = await db.users.find({"role": Role.admin.value}).to_list(length=None)
    admin_user_ids = [user["_id"] for user in admin_user_ids]
    if any(ObjectId(uid) in admin_user_ids for uid in user_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove admin users from group",
        )

    await db.users.update_many(
        {"_id": {"$in": list(map(ObjectId, user_ids))}},
        {"$pull": {"permissions": {"group_id": ObjectId(group_id)}}},
    )

    return {"detail": "Group members removed"}

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
