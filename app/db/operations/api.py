import logging
from bson import ObjectId

from app.db.schemas.user import Maintains, Permission

logger = logging.getLogger(__name__)


async def db_link_titles_to_group_bulk(
    title_ids: list[ObjectId], group_id: ObjectId, db
):
    """Link multiple titles to a group."""
    await db.titles.update_many(
        {"_id": {"$in": title_ids}},
        {"$set": {"group_id": group_id}},
    )
    await db.groups.update_one(
        {"_id": group_id},
        {
            "$addToSet": {
                "title_ids": {"$each": title_ids}
            }
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
