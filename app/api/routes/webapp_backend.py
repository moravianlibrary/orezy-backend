from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_db
from app.db.schemas import (
    Page,
    TitleCreate,
)
from fastapi.encoders import jsonable_encoder

router = APIRouter(prefix="/webapp", tags=["webapp"])


@router.post("/upload")
async def upload_title(title_data: TitleCreate, db=Depends(get_db)):
    """Uploads a new title with according files to the database."""
    pass


@router.get("/{external_id}/status")
async def get_title_state(external_id: str, db=Depends(get_db)):
    """Gets the current state of a title by its ID."""
    title = await db.titles.find_one({"external_id": external_id})
    if not title:
        raise HTTPException(404, "Title not found")

    return {"state": title.get("state"), "id": external_id}


@router.get("/{external_id}/coordinates")
async def get_coordinates(external_id: str, db=Depends(get_db)):
    """Get crop instructions for all pages."""
    title = await db.titles.find_one({"external_id": external_id})
    if not title:
        raise HTTPException(404, "Title not found")

    for page in title["pages"]:
        page["_id"] = str(page["_id"])

    return {"id": external_id, "scans": title["pages"]}


@router.get("/{external_id}/coordinates/{scan_id}")
async def get_scan_coordinates(external_id: str, scan_id: str, db=Depends(get_db)):
    """Get crop instructions for a specific file (scan)."""
    scan = await db.titles.find_one(
        {"pages._id": ObjectId(scan_id), "external_id": external_id},
        {"pages": {"$elemMatch": {"_id": ObjectId(scan_id)}}},
    )
    if not scan:
        raise HTTPException(404, "Scan not found")

    pages = scan["pages"][0]
    pages["_id"] = str(pages["_id"])
    return pages


@router.put("/{external_id}/coordinates/{scan_id}")
async def update_scan_coordinates(
    external_id: str, scan_id: str, pages: list[Page], db=Depends(get_db)
):
    """Update user edited crop instructions for a specific file (scan)."""
    pages = jsonable_encoder(pages)
    result = await db.titles.update_one(
        {"pages._id": ObjectId(scan_id), "external_id": external_id},
        {"$set": {"pages.$.user_edited_pages": pages}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Scan not found")
    return {"id": scan_id, "user_edited_pages": pages}


@router.delete("/{external_id}")
async def delete_title(external_id: str, db=Depends(get_db)):
    """Delete a title and all associated data."""
    title = await db.titles.find_one({"external_id": external_id})
    if not title:
        raise HTTPException(404, "Title not found")

    await db.titles.delete_one({"external_id": external_id})
    return {"detail": "Title and associated scans deleted"}
