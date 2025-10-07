from datetime import datetime
import logging
from app.db.schemas import PageTransformations, TaskState, Title
from bson import ObjectId

logger = logging.getLogger("auto-crop-ml")


def db_update_task_state(title_id: str, new_state: TaskState, db):
    """Update the state of a Hatchet task, store into Title object."""
    if not ObjectId.is_valid(title_id):
        raise ValueError(f"Invalid title id: {title_id}")
    result = db.titles.update_one(
        {"_id": title_id},
        {"$set": {"state": new_state, "modified_at": datetime.now()}},
    )
    if result.matched_count == 0:
        raise Exception(f"Title not found: {title_id}")

    logger.debug(f"Updated title {title_id} to state {new_state}")
    return {"status": "success", "updated_count": result.modified_count}


def db_create_title(title_data: Title, db):
    """Create a new title."""
    doc = title_data.model_dump(by_alias=True)
    result = db.titles.insert_one(doc)

    logger.debug(f"Created new title with ID: {result.inserted_id}")
    return {"title_id": str(result.inserted_id)}


def db_add_pages_bulk(title_id: str, pages_data: list[PageTransformations], db):
    """Add multiple pages to a title."""
    if not ObjectId.is_valid(title_id):
        raise ValueError(f"Invalid title id: {title_id}")

    docs = [page.model_dump(by_alias=True) for page in pages_data]

    db.titles.update_one(
        {"_id": title_id},
        {"$push": {"pages": {"$each": docs}}},
    )

    logger.debug(f"Added {len(docs)} pages to title {title_id}")
    return {"title_id": title_id, "added_count": len(docs)}
