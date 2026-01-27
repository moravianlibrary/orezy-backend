from datetime import datetime
import os
from typing import Annotated
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from app.api.limiter import limiter
from app.api.authn import get_current_user
from app.api.authz import from_group_id, from_title_id, require_group_permission
from app.api.setup_db import get_db
from app.api.utils import (
    format_page_data_list,
    format_predicted,
    resize_image,
    sniff_media_type,
)
from app.db.operations.api import db_link_titles_to_group_bulk
from app.db.schemas.title import (
    Scan,
    ScanUpdate,
    TaskState,
    Title,
    TitleCreate,
)
from app.db.schemas.user import Permission, User
from app.tasks.workflows.smartcrop_workflow import autocrop_workflow


UPLOAD_VOLUME_PATH = os.getenv("SCANS_VOLUME_PATH")
RETRAIN_VOLUME_PATH = os.getenv("RETRAIN_VOLUME_PATH")
router = APIRouter(prefix="", tags=["webapp"])


@limiter.limit("60/minute;600/hour")
@router.post(
    "/create",
    dependencies=[
        Depends(
            require_group_permission(Permission.manage, group_id_provider=from_group_id)
        )
    ],
)
async def create_title(
    request: Request,
    group_id: str,
    title_data: TitleCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db=Depends(get_db),
):
    """Creates new title object with an empty list of files. Prepares a directory in volume storage.

    Returns:
        dict: Created title ID.
    """
    if not ObjectId.is_valid(group_id):
        raise HTTPException(400, f"ID '{group_id}' is not a valid ObjectId")

    try:
        # Create title entry in DB
        created_title = title_data.model_dump(by_alias=True)
        title_dict = Title(**created_title).model_dump(by_alias=True)
        title_dict["state"] = TaskState.new
        title_dict["filelist"] = []
        title_dict["external_id"] = str(title_dict["_id"])
        title_dict["modified_by"] = current_user.email
        result = await db.titles.insert_one(title_dict)

        # Create directory for scans
        os.makedirs(
            os.path.join(UPLOAD_VOLUME_PATH, str(result.inserted_id)), exist_ok=True
        )
        # Link title to group
        await db_link_titles_to_group_bulk(
            title_ids=[result.inserted_id], group_id=ObjectId(group_id), db=db
        )
    except Exception as e:
        await delete_title(str(result.inserted_id), db)
        raise HTTPException(400, f"Invalid title data: {e}")
    return {"id": str(result.inserted_id)}


@limiter.limit("2000/minute")
@router.post(
    "/{title_id}/upload-scan",
    dependencies=[
        Depends(
            require_group_permission(Permission.manage, group_id_provider=from_title_id)
        )
    ],
)
async def upload_scan(
    request: Request,
    title_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    scan_data: UploadFile,
    db=Depends(get_db),
):
    """Uploads image (scan) to volume storage and links it to the title.

    Returns:
        dict: Title ID and filename of the uploaded scan.
    """
    if not ObjectId.is_valid(title_id):
        raise HTTPException(400, f"ID '{title_id}' is not a valid ObjectId")

    current_state = await get_title_state(title_id, db)
    if current_state != TaskState.new:
        raise HTTPException(
            400,
            f"Title is not in a valid state for uploading scans (new), current state: {current_state}",
        )

    # Save scan file to volume storage
    scan_path = os.path.join(UPLOAD_VOLUME_PATH, title_id, scan_data.filename)
    with open(scan_path, "wb") as f:
        content = await scan_data.read()
        f.write(content)

    # Update title entry in DB
    await db.titles.update_one(
        {"_id": ObjectId(title_id)},
        {
            "$push": {"filelist": scan_path},
            "$set": {"modified_at": datetime.now(), "modified_by": current_user.email},
        },
    )
    return {"id": title_id, "filename": scan_data.filename}


@limiter.limit("60/minute;600/hour")
@router.post(
    "/{title_id}/process",
    dependencies=[
        Depends(
            require_group_permission(Permission.manage, group_id_provider=from_title_id)
        )
    ],
)
async def process_title(request: Request, title_id: str, db=Depends(get_db)):
    """Moves title into state 'scheduled' and starts the ML prediction workflow.

    Returns:
        dict: Title ID and new state.
    """
    if not ObjectId.is_valid(title_id):
        raise HTTPException(400, f"ID '{title_id}' is not a valid ObjectId")

    current_state = await get_title_state(title_id, db)
    if current_state != TaskState.new:
        raise HTTPException(
            400,
            f"Title is not in a valid state for processing (new), current state: {current_state}",
        )

    title = await db.titles.find_one({"_id": ObjectId(title_id)})

    # Schedule task and update state
    try:
        await autocrop_workflow.aio_run_no_wait(input=Title(**title))
        await db.titles.update_one(
            {"_id": ObjectId(title_id)},
            {"$set": {"state": TaskState.scheduled, "modified_at": datetime.now()}},
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to schedule workflow: {e}")

    return {"state": TaskState.scheduled, "id": str(title["_id"])}


@router.get(
    "/{title_id}/status",
    dependencies=[
        Depends(
            require_group_permission(Permission.read, group_id_provider=from_title_id)
        )
    ],
)
async def get_title_state(title_id: str, db=Depends(get_db)):
    """Gets the current state of a title by its ID.

    Returns:
        str: Current state of the title.
    """
    if not ObjectId.is_valid(title_id):
        raise HTTPException(400, f"ID '{title_id}' is not a valid ObjectId")

    title = await db.titles.find_one({"_id": ObjectId(title_id)})
    if not title:
        raise HTTPException(404, "Title not found")

    return title.get("state")


@limiter.limit("2000/minute")
@router.get(
    "/{title_id}/scans",
    dependencies=[
        Depends(
            require_group_permission(Permission.read, group_id_provider=from_title_id)
        )
    ],
)
async def get_scans(
    request: Request, title_id: str, scan_id: str | None = None, db=Depends(get_db)
):
    """Gets crop instructions for all pages, can be filtered to get specific scan page by ID.

    Returns:
        list: List of scans with page crop instructions.
    """
    if not ObjectId.is_valid(title_id):
        raise HTTPException(400, f"ID '{title_id}' is not a valid ObjectId")

    if scan_id:
        title = await db.titles.find_one(
            {"scans._id": ObjectId(scan_id), "_id": ObjectId(title_id)},
            {"scans": {"$elemMatch": {"_id": ObjectId(scan_id)}}},
        )
    else:
        title = await db.titles.find_one({"_id": ObjectId(title_id)})
    if not title:
        raise HTTPException(404, "Title not found")

    scans = [Scan(**scan) for scan in title.get("scans", [])]
    scans = sorted(scans, key=lambda s: s.filename)
    title["scans"] = format_page_data_list(scans)
    title = jsonable_encoder(title, custom_encoder={ObjectId: str}, exclude=["filelist", "external_id"])

    return title


@limiter.limit("60/minute;600/hour")
@router.get(
    "/{title_id}/predicted-scans",
    dependencies=[
        Depends(
            require_group_permission(Permission.read, group_id_provider=from_title_id)
        )
    ],
)
async def get_predicted_pages(request: Request, title_id: str, db=Depends(get_db)):
    """Gets predictions for all scans (without user edits).

    Returns:
        list: List of scans with predicted page crop instructions.
    """
    if not ObjectId.is_valid(title_id):
        raise HTTPException(400, f"ID '{title_id}' is not a valid ObjectId")

    title = await db.titles.find_one({"_id": ObjectId(title_id)})
    if not title:
        raise HTTPException(404, "Title not found")

    scans = [Scan(**scan) for scan in title.get("scans", [])]
    scans = sorted(scans, key=lambda s: s.filename)
    title["scans"] = format_predicted(scans)
    title = jsonable_encoder(title, custom_encoder={ObjectId: str}, exclude=["filelist", "external_id"])
    return title


@limiter.limit("2000/minute")
@router.get(
    "/{title_id}/files",
    response_class=Response,
    dependencies=[
        Depends(
            require_group_permission(Permission.read, group_id_provider=from_title_id)
        )
    ],
)
async def get_scanfile(
    request: Request, title_id: str, scan_id: str, db=Depends(get_db)
):
    """Gets image of a specific scan.

    Returns:
        Response: Image file response.
    """
    if not ObjectId.is_valid(title_id):
        raise HTTPException(400, f"ID '{title_id}' is not a valid ObjectId")

    scan = await db.titles.find_one(
        {"scans._id": ObjectId(scan_id), "_id": ObjectId(title_id)},
        {"scans": {"$elemMatch": {"_id": ObjectId(scan_id)}}},
    )
    scan = scan["scans"][0]
    if not scan:
        raise HTTPException(404, "Scan not found")

    # Get file and filetype
    try:
        file = open(scan["filename"], "rb").read()
        media_type = sniff_media_type(file[:16])
    except Exception as e:
        raise HTTPException(500, f"Failed to read scan file: {e}")

    # Convert TIFF to JPEG on the fly
    if media_type == "image/tiff":
        media_type = "image/jpeg"
        file = resize_image(scan["filename"], (1024, 1024))
    return Response(content=file, media_type=media_type)


@limiter.limit("2000/minute")
@router.get(
    "/{title_id}/thumbnails",
    response_class=Response,
    dependencies=[
        Depends(
            require_group_permission(Permission.read, group_id_provider=from_title_id)
        )
    ],
)
async def get_thumbnail(
    request: Request, title_id: str, scan_id: str, db=Depends(get_db)
):
    """Gets a thumbnail for a specific scan of a title.

    Returns:
        list: List of thumbnail image responses.
    """
    if not ObjectId.is_valid(title_id):
        raise HTTPException(400, f"ID '{title_id}' is not a valid ObjectId")

    scan = await db.titles.find_one(
        {"scans._id": ObjectId(scan_id), "_id": ObjectId(title_id)},
        {"scans": {"$elemMatch": {"_id": ObjectId(scan_id)}}},
    )
    scan = scan["scans"][0]
    if not scan:
        raise HTTPException(404, "Scan not found")

    thumbnail = resize_image(scan["filename"])
    return Response(content=thumbnail, media_type="image/jpeg")


@limiter.limit("60/minute;600/hour")
@router.patch(
    "/{title_id}/update-pages",
    dependencies=[
        Depends(
            require_group_permission(Permission.write, group_id_provider=from_title_id)
        )
    ],
)
async def update_pages(
    request: Request,
    title_id: str,
    scans: list[ScanUpdate],
    current_user: Annotated[User, Depends(get_current_user)],
    db=Depends(get_db),
):
    """Updates predicted coordinates with user input for a given title ID.

    Returns:
        dict: Title ID.
    """
    if not ObjectId.is_valid(title_id):
        raise HTTPException(400, f"ID '{title_id}' is not a valid ObjectId")

    current_state = await get_title_state(title_id, db)
    if current_state not in [TaskState.ready, TaskState.user_approved]:
        raise HTTPException(
            400, f"Title is not in a valid state, current state: {current_state}"
        )

    for scan in scans:
        pages = [page.model_dump(by_alias=True) for page in scan.pages]

        if len(pages) == 1:
            pages[0]["type"] = "single"
        elif len(pages) == 2:
            pages[0]["type"] = "left"
            pages[1]["type"] = "right"

        result = await db.titles.update_one(
            {"_id": ObjectId(id), "scans._id": scan.id},
            {
                "$set": {
                    "scans.$.user_edited_pages": pages,
                }
            },
        )
        if result.matched_count == 0:
            raise HTTPException(404, f"Scan with id {scan.id} not found")

    # Update title state to user_approved
    await db.titles.update_one(
        {"_id": ObjectId(title_id)},
        {
            "$set": {
                "state": TaskState.user_approved,
                "modified_at": datetime.now(),
                "modified_by": current_user.email,
            }
        },
    )
    return {"id": title_id}


@limiter.limit("60/minute;600/hour")
@router.delete(
    "/{title_id}",
    dependencies=[
        Depends(
            require_group_permission(Permission.manage, group_id_provider=from_title_id)
        )
    ],
)
async def delete_title(request: Request, title_id: str, db=Depends(get_db)):
    """Deletes a title and all associated saved files."""
    if not ObjectId.is_valid(title_id):
        raise HTTPException(400, f"ID '{title_id}' is not a valid ObjectId")

    title = await db.titles.find_one({"_id": ObjectId(title_id)})
    if not title:
        raise HTTPException(404, "Title not found")

    # Delete from group
    await db.groups.update_one(
        {"_id": ObjectId(title["group_id"])},
        {"$pull": {"title_ids": ObjectId(title_id)}},
    )
    # Delete title from DB
    await db.titles.delete_one({"_id": ObjectId(title_id)})

    # Remove associated scans from volume storage
    for volume in [UPLOAD_VOLUME_PATH, RETRAIN_VOLUME_PATH]:
        if os.path.exists(os.path.join(volume, str(title["_id"]))):
            try:
                for filename in title["filelist"]:
                    os.remove(filename)
                os.rmdir(os.path.join(volume, str(title["_id"])))
            except Exception as e:
                raise HTTPException(
                    500, f"Failed to delete volume for title {title_id}: {e}"
                )
    return {"detail": "Title and associated scans deleted"}


@limiter.limit("60/minute;600/hour")
@router.patch(
    "/{title_id}/reset",
    dependencies=[
        Depends(
            require_group_permission(Permission.manage, group_id_provider=from_title_id)
        )
    ],
)
async def reset_predictions(
    request: Request,
    title_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db=Depends(get_db),
):
    """Resets all predictions for a given title ID. User edits are permanently removed from database.

    Returns:
        list: List of scans with predicted page crop instructions."""
    if not ObjectId.is_valid(title_id):
        raise HTTPException(400, f"ID '{title_id}' is not a valid ObjectId")

    result = await db.titles.update_one(
        {"_id": ObjectId(title_id)},
        {
            "$set": {
                "scans.$[].user_edited_pages": None,
                "modified_at": datetime.now(),
                "modified_by": current_user.email,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(404, f"Title with id {title_id} not found")

    return await get_scans(title_id, db)


@limiter.limit("2000/minute")
@router.get(
    "{group_id}/titles",
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

    titles = await db.titles.find(
        {"group_id": ObjectId(group_id)},
        {"_id": 1, "state": 1, "created_at": 1, "modified_at": 1},
    ).to_list(None)

    # Show most recently created titles first
    titles = sorted(titles, key=lambda x: x["created_at"], reverse=True)
    return jsonable_encoder(titles, custom_encoder={ObjectId: str})
