from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, Field
from datetime import datetime
from typing import Annotated
from enum import Enum


PyObjectId = Annotated[str, BeforeValidator(str)]


class Anomaly(str, Enum):
    missing_page = "missing_page"
    low_confidence = "low_confidence"
    aspect_ratio = "aspect_ratio_anomaly"


class TaskState(str, Enum):
    new = "new"
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class Title(BaseModel):
    id: PyObjectId = Field(alias="_id", default_factory=lambda: ObjectId())
    title_name: str
    crop_method: str
    created_at: datetime = Field(default_factory=datetime.now)
    modified_at: datetime = Field(default_factory=datetime.now)
    state: TaskState = Field(default=TaskState.new)
    pages: list["PageTransformations"] = Field(default_factory=list)


class PageTransformations(BaseModel):
    id: PyObjectId = Field(alias="_id", default_factory=lambda: ObjectId())
    filename: str
    x_center: float = 0
    y_center: float = 0
    width: float = 0
    height: float = 0
    confidence: float = 0
    angle: float = 0
    flags: list[str] = Field(default_factory=list)


class WorkflowOutput(BaseModel):
    results: list[PageTransformations]
    title_id: str | None = None
