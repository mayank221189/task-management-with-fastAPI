from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.utils.db import Base


class TaskModel(Base):
    __tablename__ = "user_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    is_completed: Mapped[bool | None] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_table.id", ondelete="CASCADE")
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_table.id", ondelete="SET NULL"), nullable=True
    )


class TaskDeletionRequest(Base):
    __tablename__ = "task_deletion_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'reassigned')",
            name="ck_task_deletion_requests_status",
        ),
        # PostgreSQL enforces this in production; SQLite mirrors the rule in tests.
        Index(
            "uq_task_deletion_requests_pending_task",
            "task_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_tasks.id", ondelete="SET NULL"), nullable=True
    )
    original_task_id: Mapped[int] = mapped_column(nullable=False)
    task_title: Mapped[str] = mapped_column(String, nullable=False)
    task_description: Mapped[str | None] = mapped_column(String, nullable=True)
    requested_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_table.id", ondelete="SET NULL"), nullable=True
    )
    requested_by_username: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    decided_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_table.id", ondelete="SET NULL"), nullable=True
    )
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reassigned_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_table.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
