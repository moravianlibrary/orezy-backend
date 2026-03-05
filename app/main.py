from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from app.api import limiter
from app.api.routes import groups, integration, titles, users, models
from app.api.setup_db import lifespan
from fastapi.openapi.utils import get_openapi
from app.db.schemas.title import TaskState
from fastapi.middleware.cors import CORSMiddleware
from app.logs import setup_logging
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

setup_logging()


app = FastAPI(title="Cropilot API", lifespan=lifespan)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
app.include_router(integration.router)
app.include_router(titles.router)
app.include_router(users.router)
app.include_router(groups.router)
app.include_router(models.router)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
        title="Cropilot API",
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
