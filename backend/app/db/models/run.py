"""Agent run ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.thread import utc_now


class Run(Base):
    """One execution initiated by a user message."""

    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_runs_thread_started", "thread_id", "started_at"),
        Index(
            "uq_runs_active_thread",
            "thread_id",
            unique=True,
            sqlite_where=text("status IN ('pending', 'running')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    user_message_id: Mapped[str | None] = mapped_column(String(36))
    assistant_message_id: Mapped[str | None] = mapped_column(String(36))
    loop_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
