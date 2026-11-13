# Task Management API

A REST API for creating, listing, retrieving, updating, and deleting tasks. It is built with FastAPI, SQLAlchemy, and PostgreSQL.

## Requirements

- Python 3.12 or newer
- PostgreSQL
- [uv](https://docs.astral.sh/uv/) (recommended), or pip

## Setup

1. Create a PostgreSQL database (the examples below use `tasks`).
2. Configure the database connection in a root-level `.env` file:

   ```env
   DB_CONNECTION_STRING=postgresql://postgres:your-password@localhost:5432/tasks
   ```

   Replace the username, password, host, port, and database name with your PostgreSQL settings. URL-encode special characters in the username or password.

3. Install the project dependencies and PostgreSQL driver:

   ```bash
   uv sync
   ```

   This installs Alembic and the PostgreSQL driver along with the other project dependencies. Alternatively, create and activate a virtual environment, then install from `requirements.txt`:

   ```bash
   python -m pip install -r requirements.txt
   ```

## Database migrations

Run the checked-in Alembic migrations from the project root to bring the database up to the latest revision:

```bash
uv run alembic upgrade head
```

**Before running this on a database with existing data, review the migration.** The currently checked-in revision, `migration/versions/d517663f18bb_add_user_id_to_task.py`, drops the `user_tasks` and `user_table` tables in its upgrade operation.

After changing SQLAlchemy models, generate a migration revision, review the generated file in `migration/versions/`, then apply it:

```bash
uv run alembic revision --autogenerate -m "describe the schema change"
uv run alembic upgrade head
```

If using pip instead of uv, run the same `alembic` commands in the activated virtual environment without the `uv run` prefix. Ensure the `.env` database connection points to the intended database before running migrations.

## Run

Start the development server from the project root:

```bash
uv run fastapi dev main.py
```

The API is available at `http://127.0.0.1:8000`. Interactive API documentation is at `http://127.0.0.1:8000/docs`.

The database itself must already exist. Run Alembic migrations before starting the application to keep the database schema up to date.

## API

All routes are prefixed with `/tasks`.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/tasks/create` | Create a task |
| `GET` | `/tasks/all-tasks` | List all tasks |
| `GET` | `/tasks/task/{task_id}` | Get a task by ID |
| `PUT` | `/tasks/task/{task_id}` | Update a task |
| `DELETE` | `/tasks/task/{task_id}` | Delete a task |

Create and update requests accept JSON with `title` and `description`; `is_completed` is optional and defaults to `false`:

```json
{
  "title": "Prepare release",
  "description": "Review and publish the next version",
  "is_completed": false
}
```

Task responses include `id`, `title`, `description`, and `is_completed`. Requests for a task ID that does not exist return `404 Not Found`.