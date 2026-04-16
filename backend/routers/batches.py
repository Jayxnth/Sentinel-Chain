from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.dependencies import verify_api_key

router = APIRouter()


@router.get("", dependencies=[Depends(verify_api_key)])
async def list_batches(
    source_vm: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    return {"message": "not implemented yet"}
