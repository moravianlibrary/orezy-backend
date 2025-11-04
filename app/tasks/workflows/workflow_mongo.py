# > Create a workflow

import logging

from pymongo import MongoClient
from app.core.rotate_net.rotate_model import rotate_pages
from app.db.operations import db_get_state, db_update_task_state, db_add_pages_bulk
from app.db.schemas import TaskState, Title, WorkflowOutput
from app.core.anomalies import (
    flag_low_confidence,
    flag_missing_pages,
    flag_ratio_anomalies,
)
from app.core.yolo_crop.crop_model import crop_images_inner, crop_images_outer
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
        _client = MongoClient(settings.mongodb_uri)  # , tlsCAFile=certifi.where())
        _db = _client.get_database(settings.mongodb_db)
    return _db


logger = logging.getLogger("auto-crop-ml")
autocrop_workflow = hatchet.workflow(name="autocrop-title-workflow")


@autocrop_workflow.task()
def crop(input: Title, ctx: Context):
    """Crops images in the input folder using the specified method."""
    current_state = db_get_state(input.id, _ensure_db())
    if current_state != TaskState.scheduled:
        ctx.log(f"Input {input.id} is not in a valid state.")
        ctx.cancel()
        return

    ctx.log(f"Starting crop with input: {input}")
    db_update_task_state(input.id, TaskState.in_progress, _ensure_db())

    if input.crop_method == "inner":
        result = crop_images_inner(input.filelist)
    else:
        result = crop_images_outer(input.filelist)

    # Serialize Pydantic objects
    result = [r.model_dump(by_alias=True) for r in result]
    return WorkflowOutput(results=result)


@autocrop_workflow.task(parents=[crop])
def rotate(input: EmptyModel, ctx: Context):
    """Rotates images based on detected bounding boxes."""
    previous_result = WorkflowOutput(results=ctx.task_output(crop)["results"])
    ctx.log(f"Starting rotate for {len(previous_result.results)} pages")

    result = rotate_pages(previous_result.results)

    # Serialize Pydantic objects
    result = [r.model_dump(by_alias=True) for r in result]
    return WorkflowOutput(results=result)


@autocrop_workflow.task(parents=[rotate])
def detect_anomalies(input: EmptyModel, ctx: Context):
    """Detects potential mistakes in the processed images."""
    previous_result = WorkflowOutput(results=ctx.task_output(rotate)["results"])
    title_id = ctx.workflow_input["id"]

    result = flag_missing_pages(previous_result.results)
    result = flag_low_confidence(result)
    result = flag_ratio_anomalies(result)

    db_add_pages_bulk(title_id, result, _ensure_db())
    db_update_task_state(title_id, TaskState.ready, _ensure_db())

    # Serialize Pydantic objects
    # scans_with_anomalies = [scan for scan in result if any(scan.flags)]
    ctx.log(f"Detected {len(result)} scans with anomalies")

    scans_with_anomalies = [r.model_dump(by_alias=True) for r in result]
    return WorkflowOutput(results=scans_with_anomalies)


@autocrop_workflow.on_failure_task()
def mark_as_failed(input: EmptyModel, ctx: Context):
    """Handles errors by updating the task state to failed."""
    title_id = ctx.workflow_input["id"]
    db_update_task_state(title_id, TaskState.failed, _ensure_db())
    ctx.log("Workflow failed, updated task state to failed.")
