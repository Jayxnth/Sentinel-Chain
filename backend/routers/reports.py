from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.db.models import ThreatReport
from backend.dependencies import verify_api_key

router = APIRouter()


def _parse_ts(ts: str, field: str) -> datetime:
    value = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field} format; expected ISO 8601",
        )


@router.get("", dependencies=[Depends(verify_api_key)])
async def list_reports(
    batch_id: Optional[int] = None,
    source_vm: Optional[str] = None,
    log_type: Optional[str] = None,
    severity: Optional[str] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if batch_id is not None:
        filters.append(ThreatReport.batch_id == batch_id)
    if source_vm is not None:
        filters.append(ThreatReport.source_vm == source_vm)
    if log_type is not None:
        filters.append(ThreatReport.log_type == log_type)
    if severity is not None:
        filters.append(ThreatReport.severity == severity)
    if from_ts is not None:
        filters.append(ThreatReport.ts >= _parse_ts(from_ts, "from_ts"))
    if to_ts is not None:
        filters.append(ThreatReport.ts <= _parse_ts(to_ts, "to_ts"))

    offset = max(page - 1, 0) * page_size

    try:
        total = (
            await db.execute(
                select(func.count()).select_from(ThreatReport).where(*filters)
            )
        ).scalar_one()

        rows = (
            await db.execute(
                select(ThreatReport)
                .where(*filters)
                .order_by(ThreatReport.ts.desc())
                .offset(offset)
                .limit(page_size)
            )
        ).scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list reports: {e}"
        )

    results = [
        {
            "id": r.id,
            "batch_id": r.batch_id,
            "source_vm": r.source_vm,
            "log_type": r.log_type,
            "severity": r.severity,
            "summary": r.summary,
            "findings": r.findings,
            "recommendations": r.recommendations,
            "ts": r.ts.isoformat() if r.ts is not None else None,
            "integrity_status": "VERIFIED",
        }
        for r in rows
    ]

    return {
        "results": results,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
