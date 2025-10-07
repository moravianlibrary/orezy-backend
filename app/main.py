from fastapi import FastAPI
from app.api.routes import integration_control
from app.api.deps import lifespan


app = FastAPI(title="FastAPI + MongoDB", lifespan=lifespan)
app.include_router(integration_control.router)


# Optional health check
@app.get("/healthz")
async def healthz():
    return {"ok": True}
