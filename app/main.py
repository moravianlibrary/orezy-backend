from fastapi import FastAPI
from app.api.routes import ndk_backend, webapp_backend
from app.api.deps import lifespan
from fastapi.openapi.utils import get_openapi
from app.db.schemas import TaskState


app = FastAPI(title="AutoCrop API", lifespan=lifespan)
app.include_router(webapp_backend.router)
app.include_router(ndk_backend.router)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="AutoCrop FastAPI",
        version="1.0.0",
        description="NDK integration endpoints",
        routes=app.routes,
    )
    # Add a custom schema
    openapi_schema["components"]["schemas"]["TaskState"] = {
        "title": "TaskState",
        "type": "string",
        "enum": [state.value for state in TaskState],
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/healthz")
async def healthz():
    return {"ok": True}
