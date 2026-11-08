from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.tasks import task_controller
from src.tasks.task_dtos import TaskResponseSchema, TaskSchemaDTO
from src.utils.db import get_db

task_router = APIRouter(prefix="/tasks")
DbSession = Annotated[Session, Depends(get_db)]


@task_router.post(
    "/create", response_model=TaskResponseSchema, status_code=status.HTTP_201_CREATED
)
def create_task_endpoint(requestBody: TaskSchemaDTO, db: DbSession):
    return task_controller.create_task(requestBody, db)


@task_router.get(
    "/all-tasks",
    response_model=list[TaskResponseSchema],
    status_code=status.HTTP_200_OK,
)
def get_all_tasks_endpoint(db: DbSession):
    return task_controller.get_all_tasks(db)


@task_router.get(
    "/task/{task_id}",
    response_model=TaskResponseSchema,
    status_code=status.HTTP_200_OK,
)
def get_task_by_id_endpoint(task_id: int, db: DbSession):
    return task_controller.get_task_by_id(task_id, db)


@task_router.put("/task/{task_id}", status_code=status.HTTP_200_OK)
def update_task_endpoint(task_id: int, requestBody: TaskSchemaDTO, db: DbSession):
    return task_controller.update_task(task_id, requestBody, db)


@task_router.delete("/task/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_by_id(task_id: int, db: DbSession):
    return task_controller.delete_task_by_id(task_id, db)
