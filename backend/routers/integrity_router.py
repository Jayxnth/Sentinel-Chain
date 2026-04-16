from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.dependencies import verify_api_key

router = APIRouter()


@router.get("", dependencies=[Depends(verify_api_key)])
async def check_integrity(
    source_vm: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return {"message": "not implemented yet"}
