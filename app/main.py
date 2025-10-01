from fastapi import FastAPI
from app.api.routes import titles
from app.api.deps import lifespan
from app.api.routes import pages


app = FastAPI(title="FastAPI + MongoDB", lifespan=lifespan)
app.include_router(titles.router)
app.include_router(pages.router)


# Optional health check
@app.get("/healthz")
async def healthz():
    return {"ok": True}
