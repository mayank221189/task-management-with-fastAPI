from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.tasks.task_dtos import TaskSchemaDTO
from src.tasks.task_models import TaskModel


def create_task(requestBody: TaskSchemaDTO, db: Session) -> dict[str, str | TaskModel]:
    # Implement the logic to create a task

    # data = requestBody.model_dump() //convert to dictionary
    # db_task = TaskModel(title=data["title"], description=data["description"], is_completed=data["is_completed"])
    # db.add(db_task)
    # db.commit()
    # db.refresh(db_task)

    db_task = TaskModel(**requestBody.model_dump())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    return db_task


def get_all_tasks(db: Session) -> list[TaskModel]:
    return db.query(TaskModel).all()


def get_task_by_id(task_id: int, db: Session):
    task = db.get(TaskModel, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    return task


def update_task(task_id: int, requestBody: TaskSchemaDTO, db: Session):
    task = db.get(TaskModel, task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
        )

    for key, value in requestBody.model_dump(exclude_unset=True).items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)
    return task


def delete_task_by_id(task_id: int, db: Session):
    task = db.get(TaskModel, task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
        )

    db.delete(task)
    db.commit()
