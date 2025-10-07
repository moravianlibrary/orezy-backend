# > Create a workflow

import logging

import certifi
from pymongo import MongoClient
from app.db.operations import db_update_task_state, db_create_title, db_add_pages_bulk
from app.db.schemas import TaskState, Title, WorkflowOutput
from app.core.anomalies import (
    flag_low_confidence,
    flag_missing_pages,
    flag_ratio_anomalies,
)
from app.core.rotate_model import rotate_images
from app.core.crop_model import crop_images_inner, crop_images_outer
from app.tasks.hatchet_client import hatchet
from app.api.deps import settings

from hatchet_sdk import (
    Context,
    EmptyModel,
)

_client = None
_db = None


def _ensure_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(settings.mongodb_uri, tlsCAFile=certifi.where())
        _db = _client.get_database(settings.mongodb_db)
    return _db


logger = logging.getLogger("auto-crop-ml")
autocrop_workflow = hatchet.workflow(name="autocrop-title-workflow")
upload_workflow = hatchet.workflow(name="upload-title-workflow")


@upload_workflow.task()
def upload(input: Title, ctx: Context):
    """Uploads a new title to the database."""
    ctx.log(
        f"Uploading new title: {input.title_name} with crop method: {input.crop_method}"
    )
    title_id = db_create_title(
        Title(title_name=input.title_name, crop_method=input.crop_method), _ensure_db()
    )
    ctx.log(f"Created title with ID: {title_id}")
    return {"title_id": title_id}


@autocrop_workflow.task()
def crop(input: Title, ctx: Context):
    """Crops images in the input folder using the specified method."""
    ctx.log(f"Starting crop with input: {input}")
    db_update_task_state(input.id, TaskState.in_progress, _ensure_db())

    if input.crop_method == "inner":
        result = crop_images_inner(input.title_name)
    else:
        result = crop_images_outer(input.title_name)

    return WorkflowOutput(results=result)


@autocrop_workflow.task(parents=[crop])
def rotate(input: EmptyModel, ctx: Context):
    """Rotates images based on detected bounding boxes."""
    previous_result = WorkflowOutput(results=ctx.task_output(crop)["results"])
    ctx.log(f"Starting rotate for {len(previous_result.results)} pages")

    result = rotate_images(previous_result.results)
    return WorkflowOutput(results=result)


@autocrop_workflow.task(parents=[rotate])
def detect_anomalies(input: EmptyModel, ctx: Context):
    """Detects potential mistakes in the processed images."""
    previous_result = WorkflowOutput(results=ctx.task_output(rotate)["results"])
    title_id = ctx.workflow_input["id"]

    result = flag_missing_pages(previous_result.results)
    result = flag_low_confidence(result)
    result = flag_ratio_anomalies(result)

    pages_with_anomalies = [r for r in result if len(r.flags) > 0]
    ctx.log(f"Detected {len(pages_with_anomalies)} pages with anomalies")

    db_add_pages_bulk(title_id, result, _ensure_db())
    db_update_task_state(title_id, TaskState.ready, _ensure_db())
    return WorkflowOutput(results=pages_with_anomalies)


@autocrop_workflow.on_failure_task()
def mark_as_failed(input: EmptyModel, ctx: Context):
    """Handles errors by updating the task state to failed."""
    title_id = ctx.workflow_input["id"]
    db_update_task_state(title_id, TaskState.failed, _ensure_db())
    ctx.log("Workflow failed, updated task state to failed.")
