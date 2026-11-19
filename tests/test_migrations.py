import importlib.util
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine

MIGRATIONS = Path(__file__).parents[1] / "migration" / "versions"
INITIAL_REVISION = MIGRATIONS / "e96db93c87ab_add_user_id_to_task.py"
FEATURE_REVISION = MIGRATIONS / "4f2c8a9d1b73_add_roles_and_deletion_reviews.py"


def apply_revision(path: Path, operations: Operations) -> None:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load migration at {path}")
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = operations  # type: ignore
    migration.upgrade()


class MigrationTests(unittest.TestCase):
    def run_revisions(self, revisions: tuple[Path, ...]) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        with engine.begin() as connection:
            operations = Operations(MigrationContext.configure(connection))
            for revision in revisions:
                apply_revision(revision, operations)
            table_names = set(sa.inspect(connection).get_table_names())
            self.assertTrue(
                {
                    "roles",
                    "user_table",
                    "user_tasks",
                    "task_deletion_requests",
                }.issubset(table_names)
            )
        engine.dispose()

    def test_fresh_database_migrations_create_all_feature_tables(self) -> None:
        self.run_revisions((INITIAL_REVISION, FEATURE_REVISION))

    def test_feature_migration_recovers_database_at_old_empty_revision(self) -> None:
        self.run_revisions((FEATURE_REVISION,))

    def test_existing_users_and_tasks_are_preserved_and_defaulted(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "CREATE TABLE user_table ("
                    "id INTEGER PRIMARY KEY, first_name VARCHAR NOT NULL, "
                    "last_name VARCHAR NOT NULL, username VARCHAR NOT NULL, "
                    "hashed_password VARCHAR NOT NULL, email VARCHAR NOT NULL, "
                    "is_active BOOLEAN NOT NULL, created_at DATETIME NOT NULL)"
                )
            )
            connection.execute(
                sa.text(
                    "CREATE TABLE user_tasks ("
                    "id INTEGER PRIMARY KEY, title VARCHAR NOT NULL, "
                    "description VARCHAR, is_completed BOOLEAN)"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO user_table VALUES "
                    "(1, 'Existing', 'User', 'existing', 'hash', "
                    "'existing@example.com', 1, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO user_tasks VALUES "
                    "(1, 'Existing task', 'Keep this task', 0)"
                )
            )
            operations = Operations(MigrationContext.configure(connection))
            apply_revision(INITIAL_REVISION, operations)
            apply_revision(FEATURE_REVISION, operations)

            existing_user = connection.execute(
                sa.text(
                    "SELECT roles.name FROM user_table "
                    "JOIN roles ON roles.id = user_table.role_id "
                    "WHERE user_table.id = 1"
                )
            ).scalar_one()
            existing_task = connection.execute(
                sa.text("SELECT title, created_by_id FROM user_tasks WHERE id = 1")
            ).one()
            self.assertEqual(existing_user, "member")
            self.assertEqual(existing_task.title, "Existing task")
            self.assertIsNone(existing_task.created_by_id)
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
