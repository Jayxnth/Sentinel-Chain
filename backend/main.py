import os

from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import init_db, get_db
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
async def health_check(db: AsyncSession = Depends(get_db)):
    """Extended health check probing database and ChromaDB connectivity."""
    health = {
        "status": "ok",
        "database": "ok",
        "chromadb": "ok"
    }

    # Check database
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        health["database"] = "error"
        health["status"] = "degraded"

    # Check ChromaDB directory
    try:
        chroma_dir = os.getenv("CHROMA_DIR", "./chroma_db")
        if not os.path.exists(chroma_dir):
            health["chromadb"] = "not_initialized"
    except Exception:
        health["chromadb"] = "error"
        health["status"] = "degraded"

    return health
