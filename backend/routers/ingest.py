from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.dependencies import verify_api_key

router = APIRouter()


class IngestRequest(BaseModel):
    source_vm: str
    log_type: str
    content: str
    filename: Optional[str] = None
    ts: str


@router.post("", dependencies=[Depends(verify_api_key)])
async def ingest(
    payload: IngestRequest,
    db: AsyncSession = Depends(get_db),
):
    return {"message": "not implemented yet"}
