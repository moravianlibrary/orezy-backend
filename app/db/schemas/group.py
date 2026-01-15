from app.db.schemas.base import BaseModelWithId


class Group(BaseModelWithId):
    short_name: str
    full_name: str
    description: str | None = None
    title_ids: list[str] = []
