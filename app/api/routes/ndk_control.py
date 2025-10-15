from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_db
from app.api.routes.utils import format_page_data
from app.db.schemas import Scan, TaskState, Title, TitleCreateNDK, TitleNDK
from starlette.responses import RedirectResponse
from pymongo.errors import DuplicateKeyError
from app.tasks.workflows.workflow_mongo import autocrop_workflow

router = APIRouter(prefix="/ndk", tags=["ndk"])


@router.post("/create")
async def create_title(title_data: TitleCreateNDK, db=Depends(get_db)):
    """Creates a new title and schedules a Hatchet workflow for it."""
    try:
        created_title = title_data.model_dump(by_alias=True)
        doc = TitleNDK(**created_title).model_dump(by_alias=True)
        if doc["external_id"] is None:
            doc["external_id"] = str(doc["_id"])
        await db.titles.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(400, "Title with this external_id already exists")
    except Exception as e:
        raise HTTPException(400, f"Invalid title data: {e}")

    # Schedule task and update state
    try:
        await autocrop_workflow.aio_run_no_wait(input=Title(**doc))
        await db.titles.update_one(
            {"external_id": doc["external_id"]},
            {"$set": {"state": TaskState.scheduled}},
        )
    except Exception as e:
        await db.titles.delete_one({"external_id": doc["external_id"]})
        raise HTTPException(500, f"Failed to schedule workflow: {e}")

    return {"state": TaskState.scheduled, "id": doc["external_id"]}


@router.get("/{external_id}/status")
async def get_title_state(external_id: str, db=Depends(get_db)):
    """Gets the current state of a title by its ID."""
    title = await db.titles.find_one({"external_id": external_id})
    if not title:
        raise HTTPException(404, "Title not found")

    return {"state": title.get("state"), "id": external_id}


@router.get("/{external_id}/open")
async def open_webapp(external_id: str, db=Depends(get_db)):
    """Opens web editor with predicted pages for the given title."""
    title = await db.titles.find_one({"external_id": external_id})
    if not title:
        raise HTTPException(404, "Title not found")

    if title.get("state") != TaskState.ready:
        raise HTTPException(
            400, f"Title is not in a ready state, current state: {title.get('state')}"
        )

    return RedirectResponse(url="https://example.com", status_code=301)


@router.get("/{external_id}/coordinates")
async def get_coordinates(external_id: str, db=Depends(get_db)):
    """Get crop instructions for all pages."""
    title = await db.titles.find_one({"external_id": external_id})

    if not title:
        raise HTTPException(404, "Title not found")

    scans = [Scan(**scan) for scan in title.get("pages", [])]
    pages = format_page_data(scans)

    return {
        "id": external_id,
        "pages": pages,
    }


@router.post("/{external_id}/complete")
async def mark_completed(external_id: str, db=Depends(get_db)):
    """Mark a title as completed."""
    title = await db.titles.find_one({"external_id": external_id})

    if not title:
        raise HTTPException(404, "Title not found")
    if title.get("state") != TaskState.ready:
        raise HTTPException(
            400, f"Title is not in a ready state, current state: {title.get('state')}"
        )

    await db.titles.update_one(
        {"external_id": external_id}, {"$set": {"state": TaskState.completed}}
    )

    return {"state": TaskState.completed, "id": external_id}
