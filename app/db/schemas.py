from bson import ObjectId
from pydantic import AfterValidator, BaseModel, BeforeValidator, Field
from pydantic.json_schema import JsonSchemaValue
from datetime import datetime
from typing import Annotated, Any
from enum import Enum
from pydantic_core import core_schema



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


class Title(BaseModel):
    id: PyObjectId = Field(alias="_id", default_factory=lambda: ObjectId())
    external_id: str | None = None
    filelist: list[str] = Field(default_factory=list)
    crop_method: CropMethod
    created_at: datetime = Field(default_factory=datetime.now)
    modified_at: datetime = Field(default_factory=datetime.now)
    state: TaskState = Field(default=TaskState.new)
    pages: list["PageTransformations"] = Field(default_factory=list)

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
    type: str | None = None


class WorkflowOutput(BaseModel):
    results: list[PageTransformations]
    title_id: str | None = None