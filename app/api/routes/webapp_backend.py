import os
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from app.api.deps import get_db, require_token
from app.api.utils import format_page_data_list, format_predicted
from app.db.schemas import (
    Scan,
    ScanUpdate,
    TaskState,
    Title,
    TitleCreate,
)
from app.tasks.workflows.workflow_mongo import autocrop_workflow
from fastapi.encoders import jsonable_encoder


VOLUME_PATH = os.getenv("SCANS_VOLUME_PATH")
router = APIRouter(prefix="", tags=["webapp"], dependencies=[Depends(require_token)])


@router.post("/create")
async def create_title(title_data: TitleCreate, db=Depends(get_db)):
    """Creates new title object with an empty list of files. Prepares a directory in volume storage.

    Returns:
        dict: Created title ID.
    """
    try:
        # Create title entry in DB
        created_title = title_data.model_dump(by_alias=True)
        title_dict = Title(**created_title).model_dump(by_alias=True)
        title_dict["state"] = "new"
        title_dict["filelist"] = []
        title_dict["external_id"] = str(title_dict["_id"])
        result = await db.titles.insert_one(title_dict)

        # Create directory for scans
        os.makedirs(os.path.join(VOLUME_PATH, str(result.inserted_id)), exist_ok=True)
    except Exception as e:
        await delete_title(str(result.inserted_id), db)
        raise HTTPException(400, f"Invalid title data: {e}")
    return {"id": str(result.inserted_id)}


@router.post("/{id}/upload-scan")
async def upload_scan(id: str, scan_data: UploadFile, db=Depends(get_db)):
    """Uploads image (scan) to volume storage and links it to the title.

    Returns:
        dict: Title ID and filename of the uploaded scan.
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(400, f"ID '{id}' is not a valid ObjectId")

    current_state = await get_title_state(id, db)
    if current_state != TaskState.new:
        raise HTTPException(
            400,
            f"Title is not in a valid state for uploading scans (new), current state: {current_state}",
        )

    # Save scan file to volume storage
    scan_path = os.path.join(VOLUME_PATH, id, scan_data.filename)
    with open(scan_path, "wb") as f:
        content = await scan_data.read()
        f.write(content)

    # Update title entry in DB
    await db.titles.update_one(
        {"_id": ObjectId(id)}, {"$push": {"filelist": scan_path}}
    )
    return {"id": id, "filename": scan_data.filename}


@router.post("/{id}/process")
async def process_title(id: str, db=Depends(get_db)):
    """Moves title into state 'scheduled' and starts the ML prediction workflow.

    Returns:
        dict: Title ID and new state.
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(400, f"ID '{id}' is not a valid ObjectId")

    current_state = await get_title_state(id, db)
    if current_state != TaskState.new:
        raise HTTPException(
            400,
            f"Title is not in a valid state for processing (new), current state: {current_state}",
        )

    title = await db.titles.find_one({"_id": ObjectId(id)})

    # Schedule task and update state
    try:
        await autocrop_workflow.aio_run_no_wait(input=Title(**title))
        await db.titles.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"state": TaskState.scheduled}},
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to schedule workflow: {e}")

    return {"state": TaskState.scheduled, "id": str(title["_id"])}


@router.get("/{id}/status")
async def get_title_state(id: str, db=Depends(get_db)):
    """Gets the current state of a title by its ID.

    Returns:
        str: Current state of the title.
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(400, f"ID '{id}' is not a valid ObjectId")

    title = await db.titles.find_one({"_id": ObjectId(id)})
    if not title:
        raise HTTPException(404, "Title not found")

    return title.get("state")


@router.get("/{id}/all-scans")
async def get_scans(id: str, db=Depends(get_db)):
    """Gets crop instructions for all pages.

    Returns:
        list: List of scans with page crop instructions.
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(400, f"ID '{id}' is not a valid ObjectId")

    title = await db.titles.find_one({"_id": ObjectId(id)})
    if not title:
        raise HTTPException(404, "Title not found")

    scans = [Scan(**scan) for scan in title.get("pages", [])]
    scans = sorted(scans, key=lambda s: s.filename)
    pages = format_page_data_list(scans)

    return pages


@router.get("/{id}/all-scans/{scan_id}")
async def get_pages_for_scan(id: str, scan_id: str, db=Depends(get_db)):
    """Gets crop instructions for a specific file (scan).

    Returns:
        dict: Scan with page crop instructions.
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(400, f"ID '{id}' is not a valid ObjectId")

    scan = await db.titles.find_one(
        {"pages._id": ObjectId(scan_id), "_id": ObjectId(id)},
        {"pages": {"$elemMatch": {"_id": ObjectId(scan_id)}}},
    )
    if not scan:
        raise HTTPException(404, "Scan not found")

    pages = format_page_data_list([Scan(**scan["pages"])])
    return pages


@router.get("/{id}/ok-scans")
async def get_ok_scans(id: str, db=Depends(get_db)):
    """Gets all OK (without flags) scans for a title.

    Returns:
        list: List of scans with page crop instructions.
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(400, f"ID '{id}' is not a valid ObjectId")

    all_scans = await get_scans(id, db)
    ok_scans = [scan for scan in all_scans if not scan["flags"]]
    return ok_scans


@router.get("/{id}/nok-scans")
async def get_flagged_scans(id: str, db=Depends(get_db)):
    """Gets all scans with flags for a title.

    Returns:
        list: List of scans with page crop instructions.
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(400, f"ID '{id}' is not a valid ObjectId")

    all_scans = await get_scans(id, db)
    flagged_scans = [scan for scan in all_scans if scan["flags"]]
    return flagged_scans


@router.get("/{id}/predicted-scans")
async def get_predicted_pages(id: str, db=Depends(get_db)):
    """Gets predictions for all scans (without user edits).

    Returns:
        list: List of scans with predicted page crop instructions.
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(400, f"ID '{id}' is not a valid ObjectId")

    title = await db.titles.find_one({"_id": ObjectId(id)})
    if not title:
        raise HTTPException(404, "Title not found")

    scans = [Scan(**scan) for scan in title.get("pages", [])]
    scans = sorted(scans, key=lambda s: s.filename)
    scans = format_predicted(scans)
    return scans


@router.get("/{id}/file/{scan_id}", response_class=Response)
async def get_scanfile(id: str, scan_id: str, db=Depends(get_db)):
    """Gets image of a specific scan.

    Returns:
        Response: Image file response.
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(400, f"ID '{id}' is not a valid ObjectId")

    scan = await db.titles.find_one(
        {"pages._id": ObjectId(scan_id), "_id": ObjectId(id)},
        {"pages": {"$elemMatch": {"_id": ObjectId(scan_id)}}},
    )
    scan = scan["pages"][0]
    if not scan:
        raise HTTPException(404, "Scan not found")

    try:
        file = open(scan["filename"], "rb").read()
    except Exception as e:
        raise HTTPException(500, f"Failed to read scan file: {e}")
    return Response(content=file, media_type="image/jpeg")


@router.patch("/{id}/update-pages")
async def update_pages(id: str, scans: list[ScanUpdate], db=Depends(get_db)):
    """Updates predicted coordinates with user input for a given title ID.

    Returns:
        dict: Title ID.
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(400, f"ID '{id}' is not a valid ObjectId")

    current_state = await get_title_state(id, db)
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
            {"_id": ObjectId(id), "pages._id": scan.id},
            {
                "$set": {
                    "pages.$.user_edited_pages": pages,
                }
            },
        )
        if result.matched_count == 0:
            raise HTTPException(404, f"Scan with id {scan.id} not found")
    return {"id": id}


@router.delete("/{id}")
async def delete_title(id: str, db=Depends(get_db)):
    """Deletes a title and all associated saved files."""
    if not ObjectId.is_valid(id):
        raise HTTPException(400, f"ID '{id}' is not a valid ObjectId")

    title = await db.titles.find_one({"_id": ObjectId(id)})
    if not title:
        raise HTTPException(404, "Title not found")

    await db.titles.delete_one({"_id": ObjectId(id)})

    # Remove associated scans from volume storage
    if os.path.exists(os.path.join(VOLUME_PATH, str(title["_id"]))):
        try:
            for filename in title["filelist"]:
                os.remove(filename)
            os.rmdir(os.path.join(VOLUME_PATH, str(title["_id"])))
        except Exception as e:
            raise HTTPException(500, f"Failed to delete volume for title {id}: {e}")
    return {"detail": "Title and associated scans deleted"}


@router.get("/title-ids")
async def get_title_ids(db=Depends(get_db)):
    """Gets all title IDs from the database.

    Returns:
        list: List of title IDs.
    """
    titles = await db.titles.find({}, {"_id": 1}).to_list(None)
    return [str(title["_id"]) for title in titles]
