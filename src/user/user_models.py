from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.utils.db import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    users: Mapped[list[User]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "user_table"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    # `default` is applied by SQLAlchemy; `server_default` also covers direct SQL inserts.
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )
    # Let the database set a timestamp if an insert does not provide one.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_table.id", ondelete="SET NULL"), nullable=True, index=True
    )

    role: Mapped[Role] = relationship(back_populates="users")
    # This self-reference uses manager_id to identify a user's manager; the options distinguish
    # the manager row from the report row and connect the inverse direct_reports collection.
    manager: Mapped[User | None] = relationship(
        remote_side=[id], back_populates="direct_reports", foreign_keys=[manager_id]
    )
    # Inverse of manager: users whose manager_id points to this user's id.
    direct_reports: Mapped[list[User]] = relationship(
        back_populates="manager", foreign_keys=[manager_id]
    )
