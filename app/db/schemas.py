from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, Field
from datetime import datetime
from typing import Annotated
from enum import Enum


# Represents an ObjectId field in the database.
# It will be represented as a `str` on the model so that it can be serialized to JSON.
PyObjectId = Annotated[str, BeforeValidator(str)]


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


class Page(BaseModel):
    xc: float
    yc: float
    width: float
    height: float
    confidence: float = 0
    angle: float = 0
    flags: list[str] = Field(default_factory=list)
    type: str | None = None


class Scan(BaseModel):
    filename: str
    id: PyObjectId = Field(alias="_id", default_factory=lambda: ObjectId())
    predicted_pages: list[Page] = Field(default_factory=list)
    user_edited_pages: list[Page] | None = None


class WorkflowOutput(BaseModel):
    results: list[Scan]
    title_id: str | None = None


class TitleCreate(BaseModel):
    external_id: str | None = None
    filelist: list[str] = Field(default_factory=list)
    crop_method: CropMethod = Field(default=CropMethod.inner)


class TitleCreateNDK(TitleCreate):
    crop_type_code: str | None = None
    double_page: bool = False
    scanner_code: str | None = None
    scan_type_code: str | None = None
    scan_mode_code: str | None = None
    color_code: str | None = None
    page_count: int | None = None
    scan_count: int | None = None
    note: str | None = None


class TitleCreateMZK(TitleCreate):
    pass


class Title(BaseModel):
    id: PyObjectId = Field(alias="_id", default_factory=lambda: ObjectId())
    external_id: str | None = None
    filelist: list[str] = Field(default_factory=list)
    crop_method: CropMethod
    created_at: datetime = Field(default_factory=datetime.now)
    modified_at: datetime = Field(default_factory=datetime.now)
    state: TaskState = Field(default=TaskState.new)
    pages: list[Scan] = Field(default_factory=list)


class TitleNDK(Title):
    crop_type_code: str | None = None
    double_page: bool = False
    scanner_code: str | None = None
    scan_type_code: str | None = None
    scan_mode_code: str | None = None
    color_code: str | None = None
    page_count: int | None = None
    scan_count: int | None = None
    note: str | None = None


class TitleMZK(Title):
    pass
