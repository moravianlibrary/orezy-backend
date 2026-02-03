import os
from fastapi import FastAPI
from app.api.routes import auth, groups, ndk_integration, titles, users
from app.api.setup_db import lifespan
from fastapi.openapi.utils import get_openapi
from app.db.schemas.title import TaskState
from fastapi.middleware.cors import CORSMiddleware
from app.logs import setup_logging

setup_logging()


app = FastAPI(title="PageTrace API", lifespan=lifespan)
if os.getenv("NDK_DEPLOYMENT", "false").lower() in ("1", "true", "yes"):
    app.include_router(ndk_integration.router)
app.include_router(titles.router)
app.include_router(users.router)
app.include_router(groups.router)
app.include_router(auth.router)

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
        version="1.0.1",
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
