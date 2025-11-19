from bson import ObjectId
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
    model_validator,
)
from datetime import datetime
from typing import Annotated, Union
from enum import Enum


def validate_object_id(value: Union[str, ObjectId]) -> ObjectId:
    if isinstance(value, ObjectId):
        return value

    if ObjectId.is_valid(value):
        return ObjectId(value)

    raise ValueError("Invalid ObjectId {value}")


ObjectIdField = Annotated[
    Union[str, ObjectId],
    AfterValidator(validate_object_id),
    PlainSerializer(lambda x: str(x), return_type=str, when_used="json"),
    WithJsonSchema({"type": "string"}, mode="serialization"),
]


class BaseModelWithId(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: ObjectIdField = Field(default_factory=ObjectId, alias="_id")


class Anomaly(str, Enum):
    page_count_mismatch = "page_count_mismatch"
    low_confidence = "low_confidence"
    dimensions = "odd_dimensions"
    prediction_error = "no_prediction"
    prediction_overlap = "prediction_overlap"


class TaskState(str, Enum):
    new = "new"
    scheduled = "scheduled"
    in_progress = "in_progress"
    ready = "ready"
    failed = "failed"
    user_approved = "user_approved"
    completed = "completed"


class CropMethod(str, Enum):
    inner = "inner"
    outer = "outer"


class Page(BaseModelWithId):
    xc: float
    yc: float
    width: float
    height: float
    confidence: float = 0
    angle: float = 0
    type: str | None = None
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def round_values(cls, values):
        """Round all numeric fields to 3 decimals."""
        for field in ("xc", "yc", "width", "height", "confidence", "angle"):
            val = getattr(values, field, None)
            if isinstance(val, (int, float)):
                setattr(values, field, round(val, 4))
        return values


class Scan(BaseModelWithId):
    filename: str
    predicted_pages: list[Page] = Field(default_factory=list)
    user_edited_pages: list[Page] | None = None


class ScanUpdate(BaseModelWithId):
    pages: list[Page]


class WorkflowOutput(BaseModel):
    results: list[Scan]
    title_id: str | None = None


class TitleCreate(BaseModel):
    external_id: str | None = None
    filelist: list[str] = Field(default_factory=list)
    crop_method: CropMethod = Field(default=CropMethod.inner)

    crop_type_code: str | None = None
    double_page: bool = False
    scanner_code: str | None = None
    scan_type_code: str | None = None
    scan_mode_code: str | None = None
    color_code: str | None = None
    page_count: int | None = None
    scan_count: int | None = None
    note: str | None = None


class Title(BaseModelWithId):
    external_id: str | None = None
    filelist: list[str] = Field(default_factory=list)
    crop_method: CropMethod
    created_at: datetime = Field(default_factory=datetime.now)
    modified_at: datetime = Field(default_factory=datetime.now)
    state: TaskState = Field(default=TaskState.new)
    scans: list[Scan] = Field(default_factory=list)

    crop_type_code: str | None = None
    double_page: bool = False
    scanner_code: str | None = None
    scan_type_code: str | None = None
    scan_mode_code: str | None = None
    color_code: str | None = None
    page_count: int | None = None
    scan_count: int | None = None
    note: str | None = None
