from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.tasks import task_controller
from src.tasks.task_dtos import (
    DeletionRequestCreateSchema,
    DeletionRequestResponseSchema,
    DeletionReviewSchema,
    TaskResponseSchema,
    TaskSchemaDTO,
)
from src.user.user_models import User
from src.utils.db import get_db
from src.utils.helpers import is_authenticated, require_roles

task_router = APIRouter(prefix="/tasks")
DbSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(is_authenticated)]
RequestingUser = Annotated[User, Depends(require_roles("member", "manager"))]
Reviewer = Annotated[User, Depends(require_roles("manager", "admin"))]
Administrator = Annotated[User, Depends(require_roles("admin"))]


@task_router.post(
    "/create", response_model=TaskResponseSchema, status_code=status.HTTP_201_CREATED
)
def create_task_endpoint(
    request_body: TaskSchemaDTO, db: DbSession, user: AuthenticatedUser
):
    return task_controller.create_task(request_body, db, user)


@task_router.get(
    "/all-tasks",
    response_model=list[TaskResponseSchema],
    status_code=status.HTTP_200_OK,
)
def get_all_tasks_endpoint(db: DbSession, user: AuthenticatedUser):
    return task_controller.get_all_tasks(db, user)


@task_router.get(
    "/task/{task_id}",
    response_model=TaskResponseSchema,
    status_code=status.HTTP_200_OK,
)
def get_task_by_id_endpoint(task_id: int, db: DbSession, user: AuthenticatedUser):
    return task_controller.get_task_by_id(task_id, db, user)


@task_router.put("/task/{task_id}", status_code=status.HTTP_200_OK)
def update_task_endpoint(
    task_id: int, request_body: TaskSchemaDTO, db: DbSession, user: AuthenticatedUser
):
    return task_controller.update_task(task_id, request_body, db, user)


@task_router.delete("/task/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_by_id(task_id: int, db: DbSession, administrator: Administrator):
    task_controller.delete_task_by_id(task_id, db, administrator)


@task_router.post(
    "/task/{task_id}/deletion-requests",
    response_model=DeletionRequestResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_task_deletion_request(
    task_id: int,
    request_body: DeletionRequestCreateSchema,
    db: DbSession,
    requester: RequestingUser,
):
    return task_controller.create_deletion_request(
        task_id, request_body.reason, db, requester
    )


@task_router.get(
    "/deletion-requests",
    response_model=list[DeletionRequestResponseSchema],
    status_code=status.HTTP_200_OK,
)
def get_deletion_requests(
    db: DbSession,
    reviewer: Reviewer,
    request_status: Literal["pending", "approved", "rejected", "reassigned"] = Query(
        default="pending", alias="status"
    ),
):
    return task_controller.list_deletion_requests(db, reviewer, request_status)


@task_router.post(
    "/deletion-requests/{request_id}/decision",
    response_model=DeletionRequestResponseSchema,
    status_code=status.HTTP_200_OK,
)
def review_task_deletion_request(
    request_id: int,
    decision: DeletionReviewSchema,
    db: DbSession,
    reviewer: Reviewer,
):
    return task_controller.review_deletion_request(request_id, decision, db, reviewer)
