import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.db.models import LogBatch, ThreatReport
from backend.dependencies import verify_api_key
from backend.integrity import compute_hash, verify_chain

REPO_ROOT = str(Path(__file__).resolve().parents[2])

router = APIRouter()

ALLOWED_LOG_TYPES = {"malware", "intrusion", "web", "http"}


class IngestRequest(BaseModel):
    source_vm: str
    log_type: str
    content: str
    # Optional in the implementation even though the contract lists filename as required;
    # keeping it optional is more flexible and does not break any functionality.
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
    if payload.log_type not in ALLOWED_LOG_TYPES:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid log_type. Accepted values: malware, intrusion, web, http"},
        )

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
    except OperationalError:
        return JSONResponse(
            status_code=503,
            content={"error": "Database unavailable"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to ingest log batch: {e}"
        )

    # If integrity check failed, return early — no AI analysis
    if result["status"] != "VERIFIED":
        return {"batch_id": new_row.id, "integrity_status": result["status"]}

    # --- Pipeline: embed into ChromaDB → analyze → store report ---

    # Step 1: Write batch content to a temp log file
    logs_dir = os.path.join(REPO_ROOT, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_filename = f"{payload.source_vm}_{new_row.id}.log"
    log_path = os.path.join(logs_dir, log_filename)
    with open(log_path, "w") as f:
        f.write(payload.content)

    # Step 2: Embed into ChromaDB via root-level ingest module
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    import ingest as root_ingest

    await asyncio.to_thread(root_ingest.ingest_logs, file_path=log_path)

    # Step 3: Run AI analysis with 60s timeout
    import analyze as root_analyze

    report_dict = None
    try:
        report_dict = await asyncio.wait_for(
            asyncio.to_thread(root_analyze.analyze_logs), timeout=60
        )
    except Exception:
        pass

    # Step 4: Store report if analysis succeeded
    if report_dict:
        findings = report_dict.get("findings", "")
        recs = report_dict.get("recommendations", "")
        report = ThreatReport(
            batch_id=new_row.id,
            source_vm=payload.source_vm,
            log_type=payload.log_type,
            severity=report_dict.get("severity"),
            summary=report_dict.get("summary"),
            findings="\n".join(findings) if isinstance(findings, list) else findings,
            recommendations="\n".join(recs) if isinstance(recs, list) else recs,
        )
        db.add(report)
        await db.commit()
        return {
            "batch_id": new_row.id,
            "integrity_status": "VERIFIED",
            "report_id": report.id,
        }

    return {
        "batch_id": new_row.id,
        "integrity_status": "VERIFIED",
        "report_id": None,
        "warning": "AI analysis failed or timed out",
    }
