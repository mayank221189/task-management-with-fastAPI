from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.tasks.task_dtos import TaskSchemaDTO
from src.tasks.task_models import TaskModel
from src.user.user_models import User


def _get_user_task(task_id: int, db: Session, user: User) -> TaskModel | None:
    statement = select(TaskModel).where(
        TaskModel.id == task_id,
        TaskModel.user_id == user.id,
    )
    return db.scalars(statement).one_or_none()


def create_task(
    requestBody: TaskSchemaDTO, db: Session, user: User
) -> dict[str, str | TaskModel]:
    # Implement the logic to create a task

    # data = requestBody.model_dump() //convert to dictionary
    # db_task = TaskModel(title=data["title"], description=data["description"], is_completed=data["is_completed"])
    # db.add(db_task)
    # db.commit()
    # db.refresh(db_task)

    db_task = TaskModel(**requestBody.model_dump(), user_id=user.id)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    return db_task


def get_all_tasks(db: Session, user: User) -> list[TaskModel]:
    return db.query(TaskModel).filter(TaskModel.user_id == user.id).all()


def get_task_by_id(task_id: int, db: Session, user: User):
    task = _get_user_task(task_id, db, user)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    return task


def update_task(task_id: int, requestBody: TaskSchemaDTO, db: Session, user: User):
    task = _get_user_task(task_id, db, user)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
        )

    for key, value in requestBody.model_dump(exclude_unset=True).items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)
    return task


def delete_task_by_id(task_id: int, db: Session, user: User):
    task = _get_user_task(task_id, db, user)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
        )

    db.delete(task)
    db.commit()
