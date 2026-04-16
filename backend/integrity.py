import hashlib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import LogBatch


def compute_hash(content: str, prev_hash: str) -> str:
    # hash the content + previous hash together to form the chain
    raw = content + ":" + prev_hash
    return hashlib.sha256(raw.encode()).hexdigest()


async def verify_chain(db: AsyncSession, source_vm: str) -> dict:

    try:
        result = await db.execute(
            select(LogBatch)
            .where(LogBatch.source_vm == source_vm)
            .order_by(LogBatch.ts.asc())
        )
        rows = result.scalars().all()
    except Exception as e:
        return {
            "status": "ERROR",
            "tampered_batch_id": None,
            "batch_count": 0,
            "last_verified_ts": None,
            "detail": str(e)
        }

    prev_hash = "0" * 64
    for row in rows:
        expected = compute_hash(row.content, prev_hash)
        if expected != row.hash:
            return {
                "status": "TAMPERED",
                "tampered_batch_id": row.id,
                "batch_count": len(rows),
                "last_verified_ts": rows[-1].ts.isoformat() if rows else None
            }
        prev_hash = row.hash

    return {
        "status": "VERIFIED",
        "tampered_batch_id": None,
        "batch_count": len(rows),
        "last_verified_ts": rows[-1].ts.isoformat() if rows else None
    }