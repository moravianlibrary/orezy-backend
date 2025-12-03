from datetime import datetime
import os
from urllib.parse import urljoin
from fastapi import APIRouter, Depends, HTTPException
import grpc
from app.api.deps import get_db, require_token
from app.api.utils import (
    copy_images_for_retraining,
    format_page_data_flat,
    get_wrong_predictions,
)
from app.db.schemas import Scan, TaskState, Title, TitleCreate
from starlette.responses import RedirectResponse
from pymongo.errors import DuplicateKeyError
from app.tasks.workflows.workflow_mongo import autocrop_workflow

router = APIRouter(prefix="/ndk", tags=["ndk"], dependencies=[Depends(require_token)])

WEBAPP_URL = os.getenv("WEBAPP_FRONTEND_URL", "https://example.com")


@router.post("/create")
async def create_title(title_data: TitleCreate, db=Depends(get_db)):
    """Creates a new title and schedules a Hatchet workflow for it."""
    try:
        created_title = title_data.model_dump(by_alias=True)
        doc = Title(**created_title).model_dump(by_alias=True)
        if doc["external_id"] is None:
            doc["external_id"] = str(doc["_id"])
        await db.titles.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(
            400, "Title with this external_id already exists", doc["external_id"]
        )
    except Exception as e:
        raise HTTPException(400, f"Invalid title data: {e}")

    # Schedule task and update state
    try:
        await autocrop_workflow.aio_run_no_wait(input=Title(**doc))
    except grpc.RpcError:
        pass  # ignore gRPC timeout, the task will be created anyway

    await db.titles.update_one(
        {"external_id": doc["external_id"]},
        {"$set": {"state": TaskState.scheduled}},
    )

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
    current_state = await get_title_state(external_id, db)
    if current_state != TaskState.ready:
        raise HTTPException(
            400, f"Title is not in a ready state, current state: {current_state}"
        )

    return RedirectResponse(
        url=urljoin(WEBAPP_URL, f"book/{external_id}"), status_code=301
    )


@router.get("/{external_id}/coordinates")
async def get_coordinates(external_id: str, db=Depends(get_db)):
    """Get crop instructions for all pages."""
    title = await db.titles.find_one({"external_id": external_id})

    if not title:
        raise HTTPException(404, "Title not found")

    scans = [Scan(**scan) for scan in title.get("scans", [])]
    pages = format_page_data_flat(scans)

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

    current_state = title.get("state")
    if current_state not in [TaskState.ready, TaskState.user_approved]:
        raise HTTPException(
            400,
            f"Title is not in an acceptable state (ready, approved), current state: {current_state}",
        )

    # Release external ID so it can be reused
    new_external_id = f"completed_{title['_id']}"

    # Check number of errors from the coordinate prediction model
    scans = [Scan(**scan) for scan in title.get("scans", [])]
    scans = sorted(scans, key=lambda s: s.filename)
    errors = get_wrong_predictions(scans)
    if (
        len(errors) > 3
    ):  # if more than 3 pages were edited by the user, save for retraining
        # Copy images for retraining, update filepaths
        retrain_filelist = copy_images_for_retraining(title["_id"], title["filelist"])
        for scan, new_file in zip(scans, retrain_filelist):
            scan.filename = new_file

        # Replace filepaths and mark for retraining
        await db.titles.update_one(
            {"external_id": external_id},
            {
                "$set": {
                    "external_id": new_external_id,
                    "filelist": retrain_filelist,
                    "scans": [scan.model_dump(by_alias=True) for scan in scans],
                    "state": TaskState.retrain,
                    "modified_at": datetime.now(),
                }
            },
        )
        return {"state": TaskState.retrain, "new_id": new_external_id}

    else:  # Title is correct, mark as completed
        await db.titles.update_one(
            {"external_id": external_id},
            {
                "$set": {
                    "external_id": new_external_id,
                    "state": TaskState.completed,
                    "modified_at": datetime.now(),
                }
            },
        )
        return {"state": TaskState.completed, "new_id": new_external_id}
