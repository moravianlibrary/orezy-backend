from pydantic import BaseModel, Field
from datetime import datetime
from typing import Annotated
from bson import ObjectId
from enum import Enum


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


Oid = Annotated[PyObjectId, Field(serialization_alias="_id")]


class TaskState(str, Enum):
    new = "new"
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class Title(BaseModel):
    title_name: str
    type: str
    created_at: datetime = Field(default_factory=datetime.now)
    modified_at: datetime = Field(default_factory=datetime.now)
    state: TaskState = Field(default=TaskState.new)
    results: list["PageTransformations"]


class PageTransformations(BaseModel):
    filename: str
    x_center: float
    y_center: float
    width: float
    height: float
    confidence: float
    angle: float
