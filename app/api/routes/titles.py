from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from fastapi.encoders import jsonable_encoder
from app.api.deps import get_db
from app.db.schemas import Title
from app.tasks.workflows.workflow_mongo import autocrop_workflow

router = APIRouter(prefix="/titles", tags=["titles"])


@router.get("/{title_id}")
async def get_title(title_id: str, db=Depends(get_db)):
    """Fetch a title by its ID."""
    if not ObjectId.is_valid(title_id):
        raise HTTPException(400, "Invalid title id")
    doc = await db.titles.find_one({"_id": ObjectId(title_id)})
    if not doc:
        raise HTTPException(404, "Title not found")
        
    return jsonable_encoder(doc, custom_encoder={ObjectId: str})


@router.get("/name/{title_name}")
async def get_title_by_name(title_name: str, db=Depends(get_db)):
    """Fetch a title by its name."""
    doc = await db.titles.find({"title_name": title_name}).to_list(length=1)
    if not doc:
        raise HTTPException(404, "Title not found")
    return jsonable_encoder(doc[0], custom_encoder={ObjectId: str})


@router.post("/")
async def prepare_title(title_data: Title, db=Depends(get_db)):
    """Create a new title."""
    doc = title_data.model_dump(exclude={"id"})
    result = await db.titles.insert_one(doc)

    # create a folder on PVC for given title, name it after ID
    return {"title_id": str(result.inserted_id)}

@router.post("/upload")
async def upload_files_bulk(db=Depends(get_db)):
    """Upload multiple files to a title."""
    # Upload files to PVC folder for given title
    return {"status": "success"}

@router.post("/finish")
async def finish_title_upload(title_id: str, db=Depends(get_db)):
    """Mark a title as prepared, run process Hatchet task."""
    title = await db.titles.find_one({"_id": ObjectId(title_id)})

    await autocrop_workflow.aio_run_no_wait(input=Title(**title))