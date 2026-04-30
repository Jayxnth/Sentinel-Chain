import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.db.models import LogBatch, ThreatReport
from backend.dependencies import verify_api_key
from backend.integrity import compute_hash, verify_chain

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

    content_str = content.decode("utf-8", errors="ignore")

    try:
        async with db.begin():
            prev_row = (
                await db.execute(
                    select(LogBatch)
                    .where(LogBatch.source_vm == source_vm)
                    .order_by(LogBatch.ts.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            prev_hash = prev_row.hash if prev_row is not None else "0" * 64
            new_hash = compute_hash(content_str, prev_hash)

            new_row = LogBatch(
                source_vm=source_vm,
                log_type=log_type,
                filename=file.filename,
                content=content_str,
                hash=new_hash,
                prev_hash=prev_hash,
                integrity_status="PENDING",
                ts=datetime.utcnow(),
            )
            db.add(new_row)
            await db.flush()

            result = await verify_chain(db, source_vm)
            new_row.integrity_status = result["status"]
    except HTTPException:
        raise
    except OperationalError:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest uploaded file: {e}")

    if result["status"] != "VERIFIED":
        return {
            "filename": file.filename,
            "status": "ingested",
            "batch_id": new_row.id,
            "integrity_status": result["status"],
        }

    # Save to logs/
    logs_dir = os.path.join(REPO_ROOT, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    save_name = f"{source_vm}_{new_row.id}_{file.filename}"
    save_path = os.path.join(logs_dir, save_name)

    async with aiofiles.open(save_path, "wb") as f:
        await f.write(content)

    # Embed into ChromaDB
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    import ingest as root_ingest

    await asyncio.to_thread(root_ingest.ingest_logs, file_path=save_path)

    # Inject batch_id into ChromaDB metadata for the just-embedded chunks
    try:
        from langchain_community.vectorstores import Chroma
        from langchain_huggingface import HuggingFaceEmbeddings

        db_dir = os.path.join(REPO_ROOT, "chroma_db")
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        vectorstore = Chroma(persist_directory=db_dir, embedding_function=embeddings)
        collection = vectorstore._collection

        target_filename = os.path.basename(save_path)

        result_meta = collection.get(where={"filename": target_filename})
        if result_meta and result_meta.get("ids"):
            new_metadatas = []
            for old_md in result_meta.get("metadatas", []):
                updated = dict(old_md) if old_md else {}
                updated["batch_id"] = new_row.id
                new_metadatas.append(updated)
            collection.update(ids=result_meta["ids"], metadatas=new_metadatas)
    except Exception as e:
        print(f"[!] Warning: failed to inject batch_id into ChromaDB metadata: {e}")

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
            batch_id=new_row.id,
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
            "batch_id": new_row.id,
            "integrity_status": "VERIFIED",
            "report_id": report.id,
        }

    return {
        "filename": file.filename,
        "status": "ingested",
        "batch_id": new_row.id,
        "integrity_status": "VERIFIED",
        "report_id": None,
        "warning": "AI analysis failed or timed out",
    }
