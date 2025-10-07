from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from app.api.deps import get_db
from app.db.schemas import TaskState, Title, TitleCreate
from app.tasks.workflows.workflow_mongo import autocrop_workflow

router = APIRouter(prefix="/control", tags=["control"])


@router.post("/create")
async def create_title(title_data: TitleCreate, db=Depends(get_db)):
    """Create a new title."""
    try:
        created_title = title_data.model_dump(by_alias=True)
        doc = Title(**created_title).model_dump(by_alias=True)
        if doc["external_id"] is None:
            doc["external_id"] = str(doc["_id"])
        result = await db.titles.insert_one(doc)
    except Exception as e:
        raise HTTPException(400, f"Invalid title data: {e}")

    return {"state": TaskState.new, "id": str(result.inserted_id)}


@router.post("/process/{external_id}")
async def process_title(external_id: str, db=Depends(get_db)):
    """Process a title by its ID."""
    title = await db.titles.find_one({"external_id": external_id})
    title.pop("_id", None)  # Remove _id to avoid issues with Pydantic

    if not title:
        raise HTTPException(404, "Title not found")
    if title.get("state") != TaskState.new:
        raise HTTPException(
            400,
            f"Title is already being processed or completed. Current state: {title.get('state')}",
        )

    # Schedule task and update state
    await autocrop_workflow.aio_run_no_wait(input=Title(**title))
    await db.titles.update_one(
        {"external_id": external_id}, {"$set": {"state": TaskState.scheduled}}
    )

    return {"state": TaskState.scheduled, "id": external_id}


@router.get("/status/{external_id}")
async def get_title_state(external_id: str, db=Depends(get_db)):
    """Get the current state of a title by its ID."""
    title = await db.titles.find_one({"external_id": external_id})
    if not title:
        raise HTTPException(404, "Title not found")

    return {"state": title.get("state"), "id": external_id}


@router.get("/coordinates/{external_id}")
async def get_coordinates(external_id: str, db=Depends(get_db)):
    """Get the coordinates of all pages for a given title."""
    title = await db.titles.find_one({"external_id": external_id})

    if not title:
        raise HTTPException(404, "Title not found")

    return {
        "id": external_id,
        "pages": jsonable_encoder(
            title["pages"], include={"filename", "xc", "yc", "width", "height", "angle", "side"}
        ),
    }


@router.post("/complete/{external_id}")
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
