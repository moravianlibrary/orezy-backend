from fastapi import FastAPI
from app.api.routes import ndk_backend, webapp_backend
from app.api.deps import lifespan
from fastapi.openapi.utils import get_openapi
from app.db.schemas import TaskState
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="PageTrace API", lifespan=lifespan)
app.include_router(ndk_backend.router)
app.include_router(webapp_backend.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="SmartCrop API",
        version="1.0.0",
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
