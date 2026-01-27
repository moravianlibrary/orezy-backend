from pydantic import BaseModel, ConfigDict, Field
from app.db.schemas.base import BaseModelWithId, ObjectIdField


class Group(BaseModelWithId):
    short_name: str
    full_name: str
    description: str | None = None
    title_ids: list[ObjectIdField] = Field(default_factory=list)


class GroupCreate(BaseModel):
    short_name: str
    full_name: str
    description: str | None = None


class GroupUpdate(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    full_name: str | None = None
    description: str | None = None
