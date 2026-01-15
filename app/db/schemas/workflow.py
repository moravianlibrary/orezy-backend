from pydantic import BaseModel
from app.db.schemas.title import Scan


class WorkflowOutput(BaseModel):
    results: list[Scan]
    title_id: str | None = None
