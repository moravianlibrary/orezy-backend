from datetime import datetime
import logging
import os
from urllib.parse import urljoin
from fastapi import APIRouter, Depends, HTTPException
import grpc
from app.api.setup_db import get_db
from app.api.authn import require_token
from app.api.utils import (
    copy_images_for_retraining,
    format_page_data_flat,
    get_wrong_predictions,
)
from app.db.operations.api import link_titles_to_group_bulk
from app.db.schemas.title import Scan, TaskState, Title, TitleCreate
from starlette.responses import RedirectResponse
from pymongo.errors import DuplicateKeyError
from app.tasks.workflows.smartcrop_workflow import autocrop_workflow

router = APIRouter(prefix="/ndk", tags=["NDK"], dependencies=[Depends(require_token)])
logger = logging.getLogger(__name__)

WEBAPP_URL = os.getenv("WEBAPP_FRONTEND_URL")


@router.post("/create")
async def create_title(title_data: TitleCreate, db=Depends(get_db)):
    """Creates a new title and schedules a Hatchet workflow for it."""
    created_title = title_data.model_dump(by_alias=True)
    group = await db.groups.find_one({"name": "NDK"})

    # Remove existing title with the same external_id, book is being rescanned
    title = await db.titles.find_one({"external_id": created_title.get("external_id")})
    if title and created_title.get("external_id"):
        await db.titles.delete_one({"external_id": created_title["external_id"]})
        await db.groups.update_one(
            {"_id": title.get("group_id")},
            {"$pull": {"title_ids": title["_id"]}},
        )

    try:
        doc = Title(**created_title).model_dump(by_alias=True)
        if doc["external_id"] is None:
            doc["external_id"] = str(doc["_id"])
        await db.titles.insert_one(doc)

        # Assign to the default group
        await link_titles_to_group_bulk(
            title_ids=[doc["_id"]], group_id=group["_id"], db=db
        )
    except DuplicateKeyError:
        raise HTTPException(400, "Title with this id already exists")
    except Exception as e:
        raise HTTPException(400, f"Invalid title data: {e}")

    # Schedule task and update state
    try:
        await autocrop_workflow.aio_run_no_wait(input=Title(**doc))
    except grpc.RpcError:
        logger.warning(
            f"gRPC timeout when scheduling workflow for title {doc['external_id']}"
        )
        pass  # ignore gRPC timeout, the task will be created anyway

    await db.titles.update_one(
        {"external_id": doc["external_id"]},
        {"$set": {"state": TaskState.scheduled}},
    )

    logger.info(f"Scheduled workflow for title {doc['external_id']} (id: {doc['_id']})")
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
    if title.get("state") not in [TaskState.ready, TaskState.user_approved]:
        raise HTTPException(
            400, f"Title is not in a ready state, current state: {title.get('state')}"
        )

    return RedirectResponse(
        url=urljoin(WEBAPP_URL, f"book/{title['_id']}"), status_code=301
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

    # Check number of errors from the coordinate prediction model
    scans = [Scan(**scan) for scan in title.get("scans", [])]
    scans = sorted(scans, key=lambda s: s.filename)
    errors = get_wrong_predictions(scans)
    # If more than 3 pages were edited by the user, save for retraining
    if len(errors) > 3:
        # Copy images for retraining, update filepaths
        retrain_filelist = copy_images_for_retraining(title["_id"], title["filelist"])
        for scan, new_file in zip(scans, retrain_filelist):
            scan.filename = new_file

        # Replace filepaths and mark for retraining
        await db.titles.update_one(
            {"external_id": external_id},
            {
                "$set": {
                    "filelist": retrain_filelist,
                    "scans": [scan.model_dump(by_alias=True) for scan in scans],
                    "state": TaskState.retrain,
                    "modified_at": datetime.now(),
                }
            },
        )
        return {"state": TaskState.retrain, "id": external_id}

    else:  # Title is correct, mark as completed
        await db.titles.update_one(
            {"external_id": external_id},
            {
                "$set": {
                    "state": TaskState.completed,
                    "modified_at": datetime.now(),
                }
            },
        )
        return {"state": TaskState.completed, "id": external_id}
