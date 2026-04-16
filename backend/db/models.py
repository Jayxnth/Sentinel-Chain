from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship
from sqlalchemy import ForeignKey, Text, String, DateTime, Integer
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class LogBatch(Base):
    __tablename__ = "log_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_vm: Mapped[str] = mapped_column(String(255), nullable=False)
    log_type: Mapped[str] = mapped_column(String(100))
    filename: Mapped[Optional[str]] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    integrity_status: Mapped[str] = mapped_column(String(10), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    reports: Mapped[List["ThreatReport"]] = relationship(back_populates="batch")

    def __repr__(self) -> str:
        return f"LogBatch(id={self.id!r}, source_vm={self.source_vm!r}, integrity_status={self.integrity_status!r})"


class ThreatReport(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("log_batches.id"), nullable=False)
    source_vm: Mapped[Optional[str]] = mapped_column(String(255))
    log_type: Mapped[Optional[str]] = mapped_column(String(100))
    severity: Mapped[Optional[str]] = mapped_column(String(10))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    findings: Mapped[Optional[str]] = mapped_column(Text)
    recommendations: Mapped[Optional[str]] = mapped_column(Text)  # this will be useful if we decide to implement an ai suggestion system.
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    batch: Mapped["LogBatch"] = relationship(back_populates="reports")

    def __repr__(self) -> str:
        return f"ThreatReport(id={self.id!r}, source_vm={self.source_vm!r}, severity={self.severity!r})"
        
