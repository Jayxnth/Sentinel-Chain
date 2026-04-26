from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.db.models import LogBatch
from backend.dependencies import verify_api_key

router = APIRouter()


@router.get("", dependencies=[Depends(verify_api_key)])
async def list_batches(
    source_vm: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if source_vm is not None:
        filters.append(LogBatch.source_vm == source_vm)

    offset = max(page - 1, 0) * page_size

    try:
        total = (
            await db.execute(
                select(func.count()).select_from(LogBatch).where(*filters)
            )
        ).scalar_one()

        rows = (
            await db.execute(
                select(LogBatch)
                .where(*filters)
                .order_by(LogBatch.ts.desc())
                .offset(offset)
                .limit(page_size)
            )
        ).scalars().all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list batches: {e}")

    return {
        "results": [
            {
                "id": r.id,
                "source_vm": r.source_vm,
                "log_type": r.log_type,
                "filename": r.filename,
                "integrity_status": r.integrity_status,
                "ts": r.ts.isoformat() if r.ts else None,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
