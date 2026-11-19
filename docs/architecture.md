# Task Management API architecture

This document describes the current implementation: the request path, authentication and authorization, database relationships, task deletion review workflow, and application setup.

## 1. Runtime components

```mermaid
flowchart LR
    Client["API client<br/>Postman / Swagger / frontend"]
    App["FastAPI application<br/>main.py"]

    subgraph API["HTTP API layer"]
        UserRouter["User router<br/>/user"]
        TaskRouter["Task router<br/>/tasks"]
        Auth["JWT authentication<br/>is_authenticated"]
        RoleGuard["Role dependencies<br/>require_roles"]
    end

    subgraph Logic["Application logic"]
        UserController["User controller<br/>register / login / access"]
        TaskController["Task controller<br/>task CRUD / deletion review"]
    end

    DBDependency["get_db dependency"]
    Session["SQLAlchemy Session"]
    PostgreSQL[("PostgreSQL")]
    Background["FastAPI BackgroundTasks"]
    Mail["FastMail"]
    SMTP["Configured SMTP server"]
    AdminCLI["Admin bootstrap CLI<br/>src.user.admin_cli"]
    Alembic["Alembic"]
    MigrationEnv["migration/env.py<br/>imports models into Base.metadata"]
    Revisions["Alembic revisions"]

    Client -->|"HTTP + JSON"| App
    App --> UserRouter
    App --> TaskRouter
    UserRouter --> UserController
    TaskRouter --> TaskController
    UserRouter -. "protected routes" .-> Auth
    TaskRouter -. "all /tasks routes require JWT" .-> Auth
    RoleGuard -. "checks authenticated User.role" .-> Auth
    UserRouter -. "admin-only routes" .-> RoleGuard
    TaskRouter -. "role-limited routes" .-> RoleGuard

    Auth --> DBDependency
    UserController --> DBDependency
    TaskController --> DBDependency
    DBDependency --> Session
    Session --> PostgreSQL

    UserController -. "registration email" .-> Background
    Background --> Mail
    Mail --> SMTP

    AdminCLI --> Session
    Alembic --> MigrationEnv
    MigrationEnv --> Revisions
    Revisions --> PostgreSQL
```

### Request handling

1. `main.py` creates the FastAPI app and includes the user and task routers. It does not create or migrate database tables at startup.
2. FastAPI validates request bodies with Pydantic DTOs and injects a database session through `get_db`.
3. **Every `/tasks` route requires authentication.** The client sends `Authorization: JWT <token>`; `is_authenticated` verifies the token and loads the current `User` from PostgreSQL. There are no public task endpoints.
4. Role-restricted routes use `require_roles`. The user's role is read from the database, rather than trusted from a JWT role claim.
5. Router functions call the corresponding controller. Controllers enforce task ownership and workflow rules, then read or update SQLAlchemy models.
6. `get_db` closes the request's SQLAlchemy session when the request finishes.

Registration hashes passwords with `pwdlib` and queues a welcome email with FastAPI `BackgroundTasks`. Email delivery is handled by `FastMail` and the configured SMTP server.

### Task endpoint access

Every endpoint below requires a valid `Authorization: JWT <token>` header. Routes with a role restriction also return `403 Forbidden` when the authenticated user's role is not allowed.

| Method | Endpoint | Allowed role(s) |
| --- | --- | --- |
| `POST` | `/tasks/create` | Any authenticated user |
| `GET` | `/tasks/all-tasks` | Any authenticated user |
| `GET` | `/tasks/task/{task_id}` | Any authenticated user |
| `PUT` | `/tasks/task/{task_id}` | Any authenticated user |
| `DELETE` | `/tasks/task/{task_id}` | `admin` |
| `POST` | `/tasks/task/{task_id}/deletion-requests` | `member`, `manager` |
| `GET` | `/tasks/deletion-requests` | `manager`, `admin` |
| `POST` | `/tasks/deletion-requests/{request_id}/decision` | `manager`, `admin` |

## 2. Authentication and authorization

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant Router as FastAPI router
    participant UserController as User controller
    participant Auth as is_authenticated / require_roles
    participant DB as PostgreSQL
    participant Controller as Task or access controller

    Client->>Router: POST /user/login (username, password)
    Router->>UserController: user_login(...)
    UserController->>DB: Find user by username
    DB-->>UserController: User + password hash + active status
    UserController->>UserController: Verify password and sign JWT
    UserController-->>Client: { "token": "..." }

    Client->>Router: Protected request + Authorization: JWT token
    Router->>Auth: Resolve authenticated user
    Auth->>Auth: Verify JWT signature and expiry
    Auth->>DB: Load current user and role
    DB-->>Auth: User and role
    Auth->>Auth: Check required role, if route is restricted
    Auth-->>Router: Authenticated User
    Router->>Controller: Call operation with user and DB session
    Controller->>DB: Read/write data
    DB-->>Controller: Result
    Controller-->>Client: HTTP response
```

The JWT contains the user's identity and expiry. It does not carry an authoritative role; role changes in the database therefore take effect on subsequent requests without trusting a stale role claim.

### Role responsibilities

| Role | Main capabilities |
| --- | --- |
| `member` | Create, view, and update tasks assigned to them; request review to delete an assigned task. Cannot directly delete tasks. |
| `manager` | Member capabilities plus review requests from their direct reports and reassign a task to another eligible active member they manage. |
| `admin` | Assign roles and managers, list users and roles, directly delete tasks, and review requests from users with no manager. |

Public registration always assigns `member`. The built-in role records are seeded by the migration. An administrator assigns a role and an optional `manager_id` through `PATCH /user/users/{user_id}/access`. The first administrator is bootstrapped by promoting an existing account with `uv run python -m src.user.admin_cli <username>`.

## 3. Database relationships

```mermaid
erDiagram
    ROLE ||--o{ USER : "assigned role"
    USER o|--o{ USER : "manager / direct reports"
    USER o|--o{ TASK : "current assignee"
    USER o|--o{ TASK : "creator"
    TASK o|--o{ TASK_DELETION_REQUEST : "current task link"
    USER o|--o{ TASK_DELETION_REQUEST : "requester"
    USER o|--o{ TASK_DELETION_REQUEST : "reviewer"
    USER o|--o{ TASK_DELETION_REQUEST : "reassignment target"

    ROLE {
        int id PK
        string name UK
    }

    USER {
        int id PK
        string username UK
        string email UK
        string hashed_password
        boolean is_active
        datetime created_at
        int role_id FK
        int manager_id FK "nullable, points to user_table.id"
    }

    TASK {
        int id PK
        string title
        string description "nullable"
        boolean is_completed "nullable"
        int user_id FK "current assignee, nullable"
        int created_by_id FK "nullable"
    }

    TASK_DELETION_REQUEST {
        int id PK
        int task_id FK "nullable after deletion"
        int original_task_id "audit snapshot"
        string task_title "audit snapshot"
        string task_description "audit snapshot, nullable"
        int requested_by_id FK "nullable"
        string requested_by_username "audit snapshot"
        string reason "nullable"
        string status
        int decided_by_id FK "nullable"
        string decision_note "nullable"
        int reassigned_to_id FK "nullable"
        datetime created_at
        datetime resolved_at "nullable"
    }
```

### Relationship details

- `USER.role_id` points to one built-in role.
- `USER.manager_id` is a nullable self-reference. One user has at most one manager; one manager can have many direct reports. A manager assignment must reference an active user with the manager role, and the API rejects cycles.
- `TASK.user_id` identifies the task's current assignee. Reassignment changes this field. `created_by_id` retains the creator separately.
- A deletion request snapshots task and requester details so the review history remains useful after the task is deleted. On approval, `task_id` is set to `NULL`, `original_task_id` remains, then the task is deleted.
- A partial unique index permits at most one `pending` deletion request per task. Resolved requests remain as audit records.

## 4. Task deletion review flow

```mermaid
flowchart TD
    Start["Member or manager asks to delete an assigned task"]
    Auth["JWT and role check"]
    Ownership{"Is the task assigned to requester?"}
    Create["Create pending request<br/>snapshot task details"]
    Unique["Database partial unique index<br/>one pending request per task"]
    ManagerCheck{"Does requester have a manager?"}
    ManagerQueue["Current manager reviews<br/>direct reports only"]
    AdminQueue["Admin reviews<br/>unassigned users only"]
    Decision{"Review decision"}
    Approve["Approve deletion<br/>mark approved, unlink task, delete task"]
    Reject["Reject request<br/>task stays assigned"]
    Reassign["Reassign request<br/>task.user_id moves to eligible member"]
    Audit["Resolved request retained<br/>with decision and snapshots"]
    DirectDelete["Admin direct DELETE<br/>pending requests are closed"]

    Start --> Auth --> Ownership
    Ownership -- "No" --> NotFound["404 Not Found"]
    Ownership -- "Yes" --> Create --> Unique --> ManagerCheck
    ManagerCheck -- "Yes" --> ManagerQueue
    ManagerCheck -- "No" --> AdminQueue
    ManagerQueue --> Decision
    AdminQueue --> Decision
    Decision -- "approve_delete" --> Approve --> Audit
    Decision -- "reject" --> Reject --> Audit
    Decision -- "reassign" --> Reassign --> Audit
    DirectDelete --> Audit
```

### Review rules

1. Members and managers may request deletion only for a task currently assigned to themselves.
2. Direct `DELETE /tasks/task/{task_id}` is restricted to administrators. Members and managers receive `403` and must use the review endpoint.
3. A manager can list and decide requests only for users whose current `manager_id` points to that manager. If a member's manager changes while a request is pending, the new manager owns the review.
4. A manager may reassign only to another active member they manage. An administrator handling an unassigned requester may reassign to any active member.
5. A pending request can be resolved once. Repeating a decision returns a conflict rather than applying a second action.

### Workflow endpoints

| Operation | Endpoint |
| --- | --- |
| Submit deletion request | `POST /tasks/task/{task_id}/deletion-requests` |
| List review requests (pending by default) | `GET /tasks/deletion-requests?status=pending` |
| Decide (approve, reject, or reassign) | `POST /tasks/deletion-requests/{request_id}/decision` |
| Admin-only direct delete | `DELETE /tasks/task/{task_id}` |

## 5. Schema setup and supporting processes

```mermaid
flowchart LR
    Config[".env<br/>DB URL, JWT, mail settings"]
    MigrationCommand["uv run alembic upgrade head"]
    AlembicEnv["migration/env.py<br/>imports all model modules"]
    Revisions["Ordered Alembic revisions<br/>create/repair base schema<br/>seed roles<br/>add manager and review schema"]
    DB[("PostgreSQL")]
    Server["uv run fastapi dev main.py"]
    Register["Register initial account<br/>defaults to member"]
    Bootstrap["uv run python -m src.user.admin_cli username"]
    AdminAPI["Admin assigns manager and roles"]

    Config --> MigrationCommand
    MigrationCommand --> AlembicEnv --> Revisions --> DB
    Config --> Server
    Server --> DB
    Server --> Register --> DB
    Bootstrap --> DB
    AdminAPI --> DB
```

The intended order is to create/configure the PostgreSQL database, run Alembic migrations, start the FastAPI server, register the initial account, and promote that account to admin with the CLI. The CLI promotes an existing user; it does not create a user. Later role and manager assignments are performed through the authenticated admin API.

## 6. Code map

| Area | Main files |
| --- | --- |
| App and routers | [`main.py`](../main.py), [`src/user/user_router.py`](../src/user/user_router.py), [`src/tasks/task_router.py`](../src/tasks/task_router.py) |
| Authentication and role guards | [`src/utils/helpers.py`](../src/utils/helpers.py) |
| User and role operations | [`src/user/user_controller.py`](../src/user/user_controller.py), [`src/user/user_models.py`](../src/user/user_models.py), [`src/user/user_dtos.py`](../src/user/user_dtos.py) |
| Task and deletion-review operations | [`src/tasks/task_controller.py`](../src/tasks/task_controller.py), [`src/tasks/task_models.py`](../src/tasks/task_models.py), [`src/tasks/task_dtos.py`](../src/tasks/task_dtos.py) |
| Database session and settings | [`src/utils/db.py`](../src/utils/db.py), [`src/utils/settings.py`](../src/utils/settings.py) |
| Email | [`src/utils/mail.py`](../src/utils/mail.py) |
| Admin bootstrap | [`src/user/admin_cli.py`](../src/user/admin_cli.py) |
| Migration configuration and revisions | [`migration/env.py`](../migration/env.py), [`migration/versions/`](../migration/versions/) |
