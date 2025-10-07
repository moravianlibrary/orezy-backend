from bson import ObjectId
from pydantic import AfterValidator, BaseModel, Field
from datetime import datetime
from typing import Annotated
from enum import Enum


def check_object_id(value: str) -> str:
    if not ObjectId.is_valid(value):
        raise ValueError(f"ID is not a valid ObjectId: {value}")
    return value


PyObjectId = Annotated[str, AfterValidator(check_object_id)]


class Anomaly(str, Enum):
    missing_page = "missing_page"
    low_confidence = "low_confidence"
    aspect_ratio = "aspect_ratio_anomaly"


class TaskState(str, Enum):
    new = "new"
    scheduled = "scheduled"
    in_progress = "in_progress"
    ready = "ready"
    failed = "failed"
    completed = "completed"


class CropMethod(str, Enum):
    inner = "inner"
    outer = "outer"


class TitleCreate(BaseModel):
    external_id: str | None = None
    filelist: list[str] = Field(default_factory=list)
    title_name: str
    crop_method: CropMethod


class Title(BaseModel):
    id: PyObjectId = Field(alias="_id", default_factory=lambda: ObjectId())
    external_id: str | None = None
    filelist: list[str] = Field(default_factory=list)
    title_name: str
    crop_method: CropMethod
    created_at: datetime = Field(default_factory=datetime.now)
    modified_at: datetime = Field(default_factory=datetime.now)
    state: TaskState = Field(default=TaskState.new)
    pages: list["PageTransformations"] = Field(default_factory=list)


class PageTransformations(BaseModel):
    id: PyObjectId = Field(alias="_id", default_factory=lambda: ObjectId())
    filename: str
    xc: float = 0
    yc: float = 0
    width: float = 0
    height: float = 0
    confidence: float = 0
    angle: float = 0
    flags: list[str] = Field(default_factory=list)
    side: str | None = None


class WorkflowOutput(BaseModel):
    results: list[PageTransformations]
    title_id: str | None = None
