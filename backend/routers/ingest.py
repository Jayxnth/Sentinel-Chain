from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.db.models import LogBatch
from backend.dependencies import verify_api_key
from backend.integrity import compute_hash, verify_chain

router = APIRouter()


class IngestRequest(BaseModel):
    source_vm: str
    log_type: str
    content: str
    filename: Optional[str] = None
    ts: str


def _parse_ts(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


@router.post("", dependencies=[Depends(verify_api_key)])
async def ingest(
    payload: IngestRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        ts = _parse_ts(payload.ts)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid ts format; expected ISO 8601 (e.g. 2026-04-07T12:00:00Z)",
        )

    try:
        async with db.begin():
            prev_row = (
                await db.execute(
                    select(LogBatch)
                    .where(LogBatch.source_vm == payload.source_vm)
                    .order_by(LogBatch.ts.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            prev_hash = prev_row.hash if prev_row is not None else "0" * 64
            new_hash = compute_hash(payload.content, prev_hash)

            new_row = LogBatch(
                source_vm=payload.source_vm,
                log_type=payload.log_type,
                filename=payload.filename,
                content=payload.content,
                hash=new_hash,
                prev_hash=prev_hash,
                integrity_status="PENDING",
                ts=ts,
            )
            db.add(new_row)
            await db.flush()

            result = await verify_chain(db, payload.source_vm)
            new_row.integrity_status = result["status"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to ingest log batch: {e}"
        )

    return {"batch_id": new_row.id, "integrity_status": result["status"]}
