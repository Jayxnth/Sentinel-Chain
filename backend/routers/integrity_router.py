from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.db.models import LogBatch
from backend.dependencies import verify_api_key
from backend.integrity import verify_chain

router = APIRouter()


@router.get("", dependencies=[Depends(verify_api_key)])
async def check_integrity(
    source_vm: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        if source_vm is not None:
            exists = (
                await db.execute(
                    select(LogBatch.id)
                    .where(LogBatch.source_vm == source_vm)
                    .limit(1)
                )
            ).scalar_one_or_none()
            vms = [source_vm] if exists is not None else []
        else:
            vms = (
                await db.execute(
                    select(LogBatch.source_vm).distinct()
                )
            ).scalars().all()
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")

    return {vm: await verify_chain(db, vm) for vm in vms}
