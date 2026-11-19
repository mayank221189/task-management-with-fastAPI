"""Add role assignments and task deletion reviews.

Revision ID: 4f2c8a9d1b73
Revises: e96db93c87ab
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4f2c8a9d1b73"
down_revision: str | Sequence[str] | None = "e96db93c87ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_NAMES = ("admin", "manager", "member")


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _ensure_base_tables() -> None:
    tables = set(_inspector().get_table_names())
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

    tables = set(_inspector().get_table_names())
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


def _ensure_foreign_key(
    table_name: str,
    constraint_name: str,
    local_column: str,
    referred_table: str,
    referred_column: str,
    ondelete: str | None = None,
) -> None:
    foreign_keys = _inspector().get_foreign_keys(table_name)
    if any(
        foreign_key["constrained_columns"] == [local_column]
        for foreign_key in foreign_keys
    ):
        return
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.create_foreign_key(
            constraint_name,
            referred_table,
            [local_column],
            [referred_column],
            ondelete=ondelete,
        )


def _ensure_column(
    table_name: str, column_name: str, column: sa.Column[object]
) -> None:
    columns = {column["name"] for column in _inspector().get_columns(table_name)}
    if column_name not in columns:
        op.add_column(table_name, column)


def _ensure_index(
    index_name: str, table_name: str, column_name: str, unique: bool = False
) -> None:
    indexes = {
        index["name"]
        for index in _inspector().get_indexes(table_name)
        if index.get("name") is not None
    }
    if index_name not in indexes:
        op.create_index(index_name, table_name, [column_name], unique=unique)


def upgrade() -> None:
    _ensure_base_tables()

    tables = set(_inspector().get_table_names())
    if "roles" not in tables:
        op.create_table(
            "roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=32), nullable=False, unique=True),
        )

    roles = sa.Table(
        "roles",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=32)),
    )
    connection = op.get_bind()
    for role_name in ROLE_NAMES:
        role_id = connection.execute(
            sa.select(roles.c.id).where(roles.c.name == role_name)
        ).scalar_one_or_none()
        if role_id is None:
            connection.execute(roles.insert().values(name=role_name))

    _ensure_column(
        "user_table",
        "role_id",
        sa.Column("role_id", sa.Integer(), nullable=True),
    )
    _ensure_column(
        "user_table",
        "manager_id",
        sa.Column("manager_id", sa.Integer(), nullable=True),
    )
    _ensure_foreign_key(
        "user_table", "fk_user_table_role_id_roles", "role_id", "roles", "id"
    )
    _ensure_foreign_key(
        "user_table",
        "fk_user_table_manager_id_user_table",
        "manager_id",
        "user_table",
        "id",
        ondelete="SET NULL",
    )

    member_role_id = connection.execute(
        sa.select(roles.c.id).where(roles.c.name == "member")
    ).scalar_one()
    user_table = sa.Table(
        "user_table",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("role_id", sa.Integer()),
    )
    connection.execute(
        user_table.update()
        .where(user_table.c.role_id.is_(None))
        .values(role_id=member_role_id)
    )
    with op.batch_alter_table("user_table") as batch_op:
        batch_op.alter_column(
            "role_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

    _ensure_column(
        "user_tasks",
        "user_id",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    _ensure_foreign_key(
        "user_tasks",
        "fk_user_tasks_user_id_user_table",
        "user_id",
        "user_table",
        "id",
        ondelete="CASCADE",
    )
    _ensure_column(
        "user_tasks",
        "created_by_id",
        sa.Column("created_by_id", sa.Integer(), nullable=True),
    )
    _ensure_foreign_key(
        "user_tasks",
        "fk_user_tasks_created_by_id_user_table",
        "created_by_id",
        "user_table",
        "id",
        ondelete="SET NULL",
    )
    task_table = sa.Table(
        "user_tasks",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer()),
        sa.Column("created_by_id", sa.Integer()),
    )
    connection.execute(
        task_table.update()
        .where(task_table.c.created_by_id.is_(None))
        .values(created_by_id=task_table.c.user_id)
    )

    for index_name, column_name, unique in (
        ("ix_user_table_id", "id", False),
        ("ix_user_table_username", "username", True),
        ("ix_user_table_email", "email", True),
        ("ix_user_table_manager_id", "manager_id", False),
    ):
        _ensure_index(index_name, "user_table", column_name, unique)

    tables = set(_inspector().get_table_names())
    if "task_deletion_requests" not in tables:
        op.create_table(
            "task_deletion_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("task_id", sa.Integer(), nullable=True),
            sa.Column("original_task_id", sa.Integer(), nullable=False),
            sa.Column("task_title", sa.String(), nullable=False),
            sa.Column("task_description", sa.String(), nullable=True),
            sa.Column("requested_by_id", sa.Integer(), nullable=True),
            sa.Column("requested_by_username", sa.String(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column(
                "status", sa.String(length=20), nullable=False, server_default="pending"
            ),
            sa.Column("decided_by_id", sa.Integer(), nullable=True),
            sa.Column("decision_note", sa.Text(), nullable=True),
            sa.Column("reassigned_to_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                "status IN ('pending', 'approved', 'rejected', 'reassigned')",
                name="ck_task_deletion_requests_status",
            ),
            sa.ForeignKeyConstraint(
                ["task_id"], ["user_tasks.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["requested_by_id"], ["user_table.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["decided_by_id"], ["user_table.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["reassigned_to_id"], ["user_table.id"], ondelete="SET NULL"
            ),
        )
    else:
        _ensure_column(
            "task_deletion_requests",
            "task_description",
            sa.Column("task_description", sa.String(), nullable=True),
        )

    indexes = {
        index["name"] for index in _inspector().get_indexes("task_deletion_requests")
    }
    if "uq_task_deletion_requests_pending_task" not in indexes:
        op.create_index(
            "uq_task_deletion_requests_pending_task",
            "task_deletion_requests",
            ["task_id"],
            unique=True,
            postgresql_where=sa.text("status = 'pending'"),
            sqlite_where=sa.text("status = 'pending'"),
        )


def downgrade() -> None:
    tables = set(_inspector().get_table_names())
    if "task_deletion_requests" in tables:
        op.drop_table("task_deletion_requests")

    user_columns: set[str] = (
        {column["name"] for column in _inspector().get_columns("user_table")}
        if "user_table" in tables
        else set()
    )
    if "user_table" in tables:
        foreign_keys = {
            foreign_key["name"]
            for foreign_key in _inspector().get_foreign_keys("user_table")
            if foreign_key.get("name")
        }
        constraints_to_drop = [
            constraint_name
            for constraint_name in (
                "fk_user_table_manager_id_user_table",
                "fk_user_table_role_id_roles",
            )
            if constraint_name in foreign_keys
        ]
        if "ix_user_table_manager_id" in {
            index["name"] for index in _inspector().get_indexes("user_table")
        }:
            op.drop_index("ix_user_table_manager_id", table_name="user_table")
        columns_to_drop = [
            column_name
            for column_name in ("manager_id", "role_id")
            if column_name in user_columns
        ]
        if constraints_to_drop or columns_to_drop:
            with op.batch_alter_table("user_table") as batch_op:
                for constraint_name in constraints_to_drop:
                    batch_op.drop_constraint(constraint_name, type_="foreignkey")
                for column_name in columns_to_drop:
                    batch_op.drop_column(column_name)

    task_columns: set[str] = (
        {column["name"] for column in _inspector().get_columns("user_tasks")}
        if "user_tasks" in tables
        else set()
    )
    if "user_tasks" in tables and "created_by_id" in task_columns:
        foreign_keys = {
            foreign_key["name"]
            for foreign_key in _inspector().get_foreign_keys("user_tasks")
            if foreign_key.get("name")
        }
        if "fk_user_tasks_created_by_id_user_table" in foreign_keys:
            with op.batch_alter_table("user_tasks") as batch_op:
                batch_op.drop_constraint(
                    "fk_user_tasks_created_by_id_user_table", type_="foreignkey"
                )
                batch_op.drop_column("created_by_id")
        else:
            op.drop_column("user_tasks", "created_by_id")

    if "roles" in tables:
        op.drop_table("roles")
