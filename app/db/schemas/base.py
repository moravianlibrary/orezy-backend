from bson import ObjectId
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
)
from typing import Annotated, Union


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
