from fastapi import FastAPI
from contextlib import asynccontextmanager
from backend.db.database import init_db
from backend.routers import (
    ingest,
    batches,
    reports,
    query,
    integrity_router,
    upload,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
app.include_router(batches.router, prefix="/batches", tags=["batches"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(query.router, prefix="/query", tags=["query"])
app.include_router(integrity_router.router, prefix="/integrity", tags=["integrity"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])


@app.get("/health")
async def health():
    return {"status": "ok"}
