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

The original initial revision dropped the user and task tables. It has been corrected for new databases, and the role/workflow revision recreates missing base tables when upgrading a database already stamped at that revision. If a previous run of the old revision dropped data, this migration cannot recover it; restore a backup before proceeding if that data is needed.

After changing SQLAlchemy models, generate a migration revision, review the generated file in `migration/versions/`, then apply it:

```bash
uv run alembic revision --autogenerate -m "describe the schema change"
uv run alembic upgrade head
```

If using pip instead of uv, run the same `alembic` commands in the activated virtual environment without the `uv run` prefix. Ensure the `.env` database connection points to the intended database before running migrations.

## Database tables and relationships

```mermaid
erDiagram
    ROLE ||--o{ USER : "assigned role"
    USER o|--o{ USER : "manager / direct reports"
    USER o|--o{ TASK : "current assignee"
    USER o|--o{ TASK : "creator"
    TASK o|--o{ TASK_DELETION_REQUEST : "deletion history"
    USER o|--o{ TASK_DELETION_REQUEST : "requester"
    USER o|--o{ TASK_DELETION_REQUEST : "reviewer"
    USER o|--o{ TASK_DELETION_REQUEST : "reassignment target"
```

| Parent -> child | Relationship type | Belongs-to side |
| --- | --- | --- |
| `roles` -> `user_table` | One-to-many | Each user belongs to one role through `role_id`; each role can have many users. |
| `user_table` -> `user_table` (manager -> direct reports) | One-to-many, self-referential | A direct report belongs to zero or one manager through `manager_id`; a manager can have many direct reports. |
| `user_table` -> `user_tasks` (assignee) | One-to-many | A task belongs to zero or one assignee through `user_id`; a user can have many assigned tasks. |
| `user_table` -> `user_tasks` (creator) | One-to-many | A task belongs to zero or one creator through `created_by_id`; a user can create many tasks. |
| `user_tasks` -> `task_deletion_requests` | One-to-many | A deletion request can refer to zero or one current task through `task_id`; a task can have multiple request records over time. |
| `user_table` -> `task_deletion_requests` (requester, reviewer, reassignment target) | One-to-many for each role | Each request can refer to zero or one user in each role through its corresponding foreign key; a user can appear in many requests. |

There are **no many-to-many relationships** in the current schema. A user has one role (not many roles), and each task has at most one current assignee.

A task can have multiple deletion-request records over time, but only one request can be pending at once. Deletion requests retain task and user snapshots for audit history. Deleting a task sets its requests' `task_id` to `NULL`, preserving those records. Deleting a user cascades to tasks assigned to them; creator, manager, and deletion-request user references are set to `NULL` where configured.

## Run

Start the development server from the project root:

```bash
uv run fastapi dev main.py
```

The API is available at `http://127.0.0.1:8000`. Interactive API documentation is at `http://127.0.0.1:8000/docs`.

The database itself must already exist. Run Alembic migrations before starting the application to keep the database schema up to date.

All newly registered users receive the `member` role. To bootstrap the first administrator, register the account, then run:

```bash
uv run python -m src.user.admin_cli <username>
```

Only an administrator can assign roles or managers. The built-in roles are `admin`, `manager`, and `member`. Each user can have at most one manager; a manager can have multiple direct reports.

See the [architecture guide](docs/architecture.md) for diagrams of the request flow, database relationships, authentication, and deletion review process.

## API

Import [`postman/Task Management API.postman_collection.json`](postman/Task%20Management%20API.postman_collection.json) into Postman to try the endpoints. Set the collection's `baseUrl` variable if the server is running at a different address. Run **Log in** with the appropriate account; its test script saves the JWT for authenticated requests. **Create task** and **Request task deletion** save their IDs for follow-up requests.

Authenticated endpoints require the JWT in `Authorization: JWT <token>`. Obtain the token by logging in.

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/user/register` | No | Register a user |
| `POST` | `/user/login` | No | Log in and receive a JWT |
| `GET` | `/user/is-auth` | Yes | Get the authenticated user's profile |
| `GET` | `/user/roles` | Admin | List built-in roles |
| `GET` | `/user/users` | Admin | List users and their role/manager assignments |
| `PATCH` | `/user/users/{user_id}/access` | Admin | Assign a role and optionally one manager |
| `POST` | `/tasks/create` | Yes | Create a task for the authenticated user |
| `GET` | `/tasks/all-tasks` | Yes | List the authenticated user's tasks |
| `GET` | `/tasks/task/{task_id}` | Yes | Get one of the authenticated user's tasks |
| `PUT` | `/tasks/task/{task_id}` | Yes | Update one of the authenticated user's tasks |
| `DELETE` | `/tasks/task/{task_id}` | Admin | Directly delete a task |
| `POST` | `/tasks/task/{task_id}/deletion-requests` | Member or Manager | Request review to delete an assigned task |
| `GET` | `/tasks/deletion-requests` | Manager or Admin | List pending requests from direct reports; admins see requests from users with no manager |
| `POST` | `/tasks/deletion-requests/{request_id}/decision` | Manager or Admin | Approve deletion, reject it, or reassign the task |

Register with JSON containing `first_name`, `last_name`, `username`, `password`, and `email`. Login accepts `username` and `password`, and returns a `token`.

To assign a role or manager, an administrator can send `{"role": "member", "manager_id": 2}` to the access endpoint. `role` may be `member`, `manager`, or `admin`; `manager_id` may be omitted to leave the current assignment unchanged or set to `null` to remove it. Only users with the manager role can be assigned as managers.

Create and update requests accept JSON with `title`, `description`, and `is_completed`:

```json
{
  "title": "Prepare release",
  "description": "Review and publish the next version",
  "is_completed": false
}
```

`is_completed` defaults to `false` when omitted during creation. Updates use `PUT` and should include all three fields. Task responses include `id`, `title`, `description`, `is_completed`, `user_id` (the current assignee), and `created_by_id`.

Members and managers cannot directly delete tasks. They submit a deletion request with an optional reason. Their direct manager can approve deletion, reject the request (leaving the task assigned), or reassign the task to another active member they manage. Administrators review requests from users without a manager and can reassign to any active member. Resolved requests remain available as an audit record. A task that does not exist or is not assigned to the caller returns `404 Not Found`; attempting direct deletion without the admin role returns `403 Forbidden`.
