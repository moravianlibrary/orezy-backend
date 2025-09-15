from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from bson import ObjectId
from ..db import get_db

router = APIRouter(prefix="/titles", tags=["titles"])


@router.get("/{title_id}")
async def get_title(title_id: str, db=Depends(get_db)):
    if not ObjectId.is_valid(title_id):
        raise HTTPException(400, "Invalid title id")
    doc = await db.titles.find_one({"_id": ObjectId(title_id)})
    if not doc:
        raise HTTPException(404, "Title not found")
    doc["_id"] = str(doc["_id"])
    return doc


@router.get("/name/{title_name}")
async def get_title_by_name(title_name: str, db=Depends(get_db)):
    doc = await db.titles.find({"title_name": title_name})
    if not doc:
        raise HTTPException(404, "Title not found")
    return doc


async def update_task_state(title_id: str, new_state: str, db):
    if not ObjectId.is_valid(title_id):
        raise HTTPException(400, "Invalid title id")
    result = await db.titles.update_one(
        {"_id": ObjectId(title_id)},
        {"$set": {"state": new_state, "modified_at": datetime.now()}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Title not found")
    return {"status": "success", "updated_count": result.modified_count}
