"""Create the user and task tables and associate tasks with users.

Revision ID: e96db93c87ab
Revises:
Create Date: 2026-11-12 19:27:33.936581
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e96db93c87ab"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _indexes_for(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {
        index_name
        for index in inspector.get_indexes(table_name)
        if (index_name := index["name"]) is not None
    }


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "user_table" not in tables:
        op.create_table(
            "user_table",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("first_name", sa.String(), nullable=False),
            sa.Column("last_name", sa.String(), nullable=False),
            sa.Column("username", sa.String(), nullable=False),
            sa.Column("hashed_password", sa.String(), nullable=False),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    for index_name, column_name, unique in (
        ("ix_user_table_id", "id", False),
        ("ix_user_table_username", "username", True),
        ("ix_user_table_email", "email", True),
    ):
        if index_name not in _indexes_for("user_table"):
            op.create_index(
                index_name,
                "user_table",
                [column_name],
                unique=unique,
            )

    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "user_tasks" not in tables:
        op.create_table(
            "user_tasks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column(
                "is_completed", sa.Boolean(), nullable=True, server_default=sa.false()
            ),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["user_table.id"], ondelete="CASCADE"),
        )
    elif "user_id" not in {
        column["name"] for column in inspector.get_columns("user_tasks")
    }:
        op.add_column("user_tasks", sa.Column("user_id", sa.Integer(), nullable=True))
        with op.batch_alter_table("user_tasks") as batch_op:
            batch_op.create_foreign_key(
                "fk_user_tasks_user_id_user_table",
                "user_table",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "user_tasks" in tables:
        op.drop_table("user_tasks")
    if "user_table" in tables:
        op.drop_table("user_table")
