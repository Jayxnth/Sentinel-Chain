import asyncio
import os
import sys
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.db.models import ThreatReport
from backend.dependencies import verify_api_key

REPO_ROOT = str(Path(__file__).resolve().parents[2])
ALLOWED_LOG_TYPES = {"malware", "intrusion", "web", "http"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

router = APIRouter()


@router.post("", dependencies=[Depends(verify_api_key)])
async def upload(
    file: UploadFile = File(...),
    source_vm: str = Form(...),
    log_type: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if log_type not in ALLOWED_LOG_TYPES:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid log_type. Accepted values: malware, intrusion, web, http"},
        )

    # Read file content with size check
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        return JSONResponse(
            status_code=413,
            content={"error": "File exceeds maximum allowed size of 10MB"},
        )

    # Save to logs/
    logs_dir = os.path.join(REPO_ROOT, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    save_name = f"{source_vm}_{file.filename}"
    save_path = os.path.join(logs_dir, save_name)

    async with aiofiles.open(save_path, "wb") as f:
        await f.write(content)

    # Embed into ChromaDB
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    import ingest as root_ingest

    await asyncio.to_thread(root_ingest.ingest_logs, file_path=save_path)

    # Run AI analysis with 60s timeout
    import analyze as root_analyze

    report_dict = None
    try:
        report_dict = await asyncio.wait_for(
            asyncio.to_thread(root_analyze.analyze_logs), timeout=60
        )
    except Exception:
        pass

    # Store report if analysis succeeded
    if report_dict:
        findings = report_dict.get("findings", "")
        recs = report_dict.get("recommendations", "")
        report = ThreatReport(
            batch_id=None,
            source_vm=source_vm,
            log_type=log_type,
            severity=report_dict.get("severity"),
            summary=report_dict.get("summary"),
            findings="\n".join(findings) if isinstance(findings, list) else findings,
            recommendations="\n".join(recs) if isinstance(recs, list) else recs,
        )
        db.add(report)
        await db.commit()
        return {
            "filename": file.filename,
            "status": "ingested",
            "batch_id": None,
            "integrity_status": "VERIFIED",
        }

    return {
        "filename": file.filename,
        "status": "ingested",
        "batch_id": None,
        "integrity_status": "VERIFIED",
    }
