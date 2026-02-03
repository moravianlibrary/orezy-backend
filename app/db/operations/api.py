from datetime import datetime
import logging
from bson import ObjectId
from fastapi.encoders import jsonable_encoder

from app.db.schemas.group import APIkey
from app.db.schemas.user import Maintains, Permission, User

logger = logging.getLogger(__name__)


async def link_titles_to_group_bulk(title_ids: list[ObjectId], group_id: ObjectId, db):
    """Link multiple titles to a group."""
    await db.titles.update_many(
        {"_id": {"$in": title_ids}},
        {"$set": {"group_id": group_id}},
    )
    await db.groups.update_one(
        {"_id": group_id},
        {
            "$addToSet": {"title_ids": {"$each": title_ids}},
            "$set": {"modified_at": datetime.now()},
        },
    )

    logger.debug(f"Linked titles {title_ids} to group {group_id}")
    return {"title_ids": title_ids, "group_id": group_id}


async def add_users_to_group_bulk(
    group_id: ObjectId, user_ids: list[ObjectId], permission: Permission, db
):
    """Add multiple users to a group with specified permission."""
    new_permission = Maintains(group_id=group_id, permission=permission).model_dump()
    result = await db.users.update_many(
        {"_id": {"$in": user_ids}},
        {"$push": {"permissions": new_permission}},
    )

    logger.debug(
        f"Added {result.modified_count} users to group {group_id} with permission {permission}"
    )
    return {"group_id": group_id, "added_count": result.modified_count}


async def remove_users_from_group_bulk(
    group_id: ObjectId, user_ids: list[ObjectId], db
):
    """Remove multiple users from a group."""
    result = await db.users.update_many(
        {"_id": {"$in": user_ids}},
        {"$pull": {"permissions": {"group_id": group_id}}},
    )

    logger.debug(f"Removed {result.modified_count} users from group {group_id}")
    return {"group_id": group_id, "removed_count": result.modified_count}


async def get_users_in_group(group_id: ObjectId, db):
    """Get all users in a specific group."""
    users = await db.users.find(
        {"permissions.group_id": group_id},
    ).to_list(length=None)

    for user in users:
        user["permission"] = await get_user_permissions_in_group(User(**user), group_id)

    return jsonable_encoder(
        users,
        custom_encoder={ObjectId: str},
        include=["_id", "full_name", "permission"],
    )


async def get_user_permissions_in_group(current_user: User, group_id: ObjectId):
    """Get the permissions of the current user in a specific group."""
    for perm in current_user.permissions:
        if perm.group_id == group_id:
            return perm.permission
    return None


async def get_api_keys(db):
    """Get all API keys from the database."""
    api_keys = await db.api_keys.find().to_list(length=None)
    return [APIkey(**api_key) for api_key in api_keys]