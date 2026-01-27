from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.db.schemas.base import BaseModelWithId, ObjectIdField


class Group(BaseModelWithId):
    name: str
    description: str | None = None
    title_ids: list[ObjectIdField] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    modified_at: datetime = Field(default_factory=datetime.now)


class GroupCreate(BaseModel):
    name: str
    description: str | None = None


class GroupUpdate(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str | None = None
    description: str | None = None
