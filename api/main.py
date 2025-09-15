from fastapi import FastAPI
from .db import lifespan
from .routers import titles

app = FastAPI(title="FastAPI + MongoDB (Motor)", lifespan=lifespan)
app.include_router(titles.router)


# Optional health check
@app.get("/healthz")
async def healthz():
    return {"ok": True}
