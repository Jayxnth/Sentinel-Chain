import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

# Reuse M2's models and integrity logic
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.db.models import Base, LogBatch
from backend.integrity import compute_hash, verify_chain

from tamper import tamper_batch


@pytest.fixture
def db():
    """In-memory SQLite with LogBatch table."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _insert_chain(db, source_vm="vm1-linux", count=3):
    """Insert a valid hash chain of `count` batches."""
    prev_hash = "0" * 64
    for i in range(count):
        content = f"log line {i}\nanother line {i}\n"
        h = compute_hash(content, prev_hash)
        batch = LogBatch(
            source_vm=source_vm,
            log_type="intrusion",
            content=content,
            hash=h,
            prev_hash=prev_hash,
            integrity_status="VERIFIED",
        )
        db.add(batch)
        prev_hash = h
    db.commit()


def test_tamper_specific_batch(db):
    _insert_chain(db, count=3)
    original = db.execute(select(LogBatch).where(LogBatch.id == 2)).scalar_one()
    original_content = original.content
    tamper_batch(db, batch_id=2)
    db.refresh(original)
    assert original.content != original_content


def test_tamper_random_batch_for_vm(db):
    _insert_chain(db, source_vm="vm1-linux", count=5)
    contents_before = {b.id: b.content for b in db.execute(select(LogBatch)).scalars().all()}
    tamper_batch(db, source_vm="vm1-linux")
    changed = 0
    for b in db.execute(select(LogBatch)).scalars().all():
        if b.content != contents_before[b.id]:
            changed += 1
    assert changed == 1


def test_invalid_batch_id(db):
    _insert_chain(db, count=1)
    result = tamper_batch(db, batch_id=999)
    assert result is False


def test_tamper_detected_by_verify_chain(db):
    _insert_chain(db, source_vm="vm1-linux", count=3)

    # Verify chain is intact before tamper
    # verify_chain is async, but we test the sync logic directly
    prev_hash = "0" * 64
    rows = db.execute(select(LogBatch).where(LogBatch.source_vm == "vm1-linux").order_by(LogBatch.ts.asc())).scalars().all()
    for row in rows:
        expected = compute_hash(row.content, prev_hash)
        assert expected == row.hash  # chain intact
        prev_hash = row.hash

    # Tamper batch 2
    tamper_batch(db, batch_id=2)

    # Verify chain is now broken
    prev_hash = "0" * 64
    rows = db.execute(select(LogBatch).where(LogBatch.source_vm == "vm1-linux").order_by(LogBatch.ts.asc())).scalars().all()
    tampered = False
    for row in rows:
        expected = compute_hash(row.content, prev_hash)
        if expected != row.hash:
            tampered = True
            assert row.id == 2
            break
        prev_hash = row.hash
    assert tampered
