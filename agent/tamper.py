import random
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from backend.db.models import LogBatch

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def tamper_batch(db: Session, batch_id: int = None, source_vm: str = None) -> bool:
    if batch_id is not None:
        batch = db.execute(select(LogBatch).where(LogBatch.id == batch_id)).scalar_one_or_none()
    elif source_vm:
        rows = db.execute(select(LogBatch).where(LogBatch.source_vm == source_vm)).scalars().all()
        if not rows:
            logging.error("No batches found for source_vm=%s", source_vm)
            return False
        batch = random.choice(rows)
    else:
        logging.error("Must provide batch_id or source_vm")
        return False

    if not batch:
        logging.error("Batch not found (id=%s)", batch_id)
        return False

    batch.content = batch.content + "\n[TAMPERED BY TEST SCRIPT]\n"
    db.commit()
    logging.info("Tampered batch id=%d (source_vm=%s)", batch.id, batch.source_vm)
    return True


if __name__ == "__main__":
    import argparse
    from sqlalchemy import create_engine

    parser = argparse.ArgumentParser(description="Sentinel-Chain Tamper Simulation")
    parser.add_argument("--db-url", required=True, help="Database URL (e.g. postgresql://user:pass@host/db)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--batch-id", type=int, help="Tamper a specific batch by ID")
    group.add_argument("--source-vm", help="Tamper a random batch for this VM")
    args = parser.parse_args()

    engine = create_engine(args.db_url)
    with Session(engine) as session:
        tamper_batch(session, batch_id=args.batch_id, source_vm=args.source_vm)
