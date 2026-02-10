import logging
import os

from fastapi import APIRouter, Depends
from app.api.authz import in_any_group, require_group_permission
from app.db.schemas.user import Permission

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/models",
    tags=["Models"],
    dependencies=[
        Depends(
            require_group_permission(Permission.upload, group_id_provider=in_any_group)
        )
    ],
)


@router.get("")
async def list_models():
    models = os.listdir(os.environ.get("MODELS_VOLUME_PATH"))
    # remove .pt extension
    models = [model[:-3] for model in models if model.endswith(".pt")]
    return {"available_models": models}
