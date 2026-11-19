from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.tasks.task_dtos import DeletionReviewSchema, TaskSchemaDTO
from src.tasks.task_models import TaskDeletionRequest, TaskModel
from src.user.user_models import User


def _get_user_task(task_id: int, db: Session, user: User) -> TaskModel | None:
    statement = select(TaskModel).where(
        TaskModel.id == task_id,
        TaskModel.user_id == user.id,
    )
    return db.scalars(statement).one_or_none()


def create_task(request_body: TaskSchemaDTO, db: Session, user: User) -> TaskModel:
    task = TaskModel(
        **request_body.model_dump(),
        user_id=user.id,
        created_by_id=user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_all_tasks(db: Session, user: User) -> list[TaskModel]:
    return list(db.scalars(select(TaskModel).where(TaskModel.user_id == user.id)).all())


def get_task_by_id(task_id: int, db: Session, user: User) -> TaskModel:
    task = _get_user_task(task_id, db, user)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    return task


def update_task(
    task_id: int, request_body: TaskSchemaDTO, db: Session, user: User
) -> TaskModel:
    task = _get_user_task(task_id, db, user)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    for key, value in request_body.model_dump(exclude_unset=True).items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)
    return task


def delete_task_by_id(task_id: int, db: Session, administrator: User) -> None:
    task = db.get(TaskModel, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    related_requests = db.scalars(
        select(TaskDeletionRequest).where(TaskDeletionRequest.task_id == task_id)
    ).all()
    for deletion_request in related_requests:
        deletion_request.task_id = None
        if deletion_request.status == "pending":
            deletion_request.status = "rejected"
            deletion_request.decided_by_id = administrator.id
            deletion_request.decision_note = "Task deleted by an administrator"
            deletion_request.resolved_at = datetime.now(UTC)

    db.delete(task)
    db.commit()


def create_deletion_request(
    task_id: int, reason: str | None, db: Session, requester: User
) -> TaskDeletionRequest:
    task = _get_user_task(task_id, db, requester)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    deletion_request = TaskDeletionRequest(
        task_id=task.id,
        original_task_id=task.id,
        task_title=task.title,
        task_description=task.description,
        requested_by_id=requester.id,
        requested_by_username=requester.username,
        reason=reason,
        status="pending",
        created_at=datetime.now(UTC),
    )
    db.add(deletion_request)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        pending_request = db.scalar(
            select(TaskDeletionRequest).where(
                TaskDeletionRequest.task_id == task.id,
                TaskDeletionRequest.status == "pending",
            )
        )
        if pending_request is None:
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A deletion request is already pending for this task",
        ) from error
    db.refresh(deletion_request)
    return deletion_request


def list_deletion_requests(
    db: Session, reviewer: User, request_status: str
) -> list[TaskDeletionRequest]:
    statement = (
        select(TaskDeletionRequest)
        .join(
            User,
            TaskDeletionRequest.requested_by_id == User.id,
        )
        .where(TaskDeletionRequest.status == request_status)
        .order_by(TaskDeletionRequest.created_at, TaskDeletionRequest.id)
    )
    if reviewer.role.name == "manager":
        statement = statement.where(User.manager_id == reviewer.id)
    else:
        statement = statement.where(User.manager_id.is_(None))
    return list(db.scalars(statement).all())


def review_deletion_request(
    request_id: int,
    decision: DeletionReviewSchema,
    db: Session,
    reviewer: User,
) -> TaskDeletionRequest:
    deletion_request = db.scalar(
        select(TaskDeletionRequest)
        .where(TaskDeletionRequest.id == request_id)
        .with_for_update()
    )
    if deletion_request is None:
        raise HTTPException(status_code=404, detail="Deletion request not found")

    requester = (
        db.scalar(
            select(User)
            .where(User.id == deletion_request.requested_by_id)
            .with_for_update()
        )
        if deletion_request.requested_by_id is not None
        else None
    )
    if requester is None:
        raise HTTPException(status_code=404, detail="Deletion request not found")
    if reviewer.role.name == "manager":
        can_review = requester.manager_id == reviewer.id
    else:
        can_review = requester.manager_id is None
    if not can_review:
        raise HTTPException(status_code=404, detail="Deletion request not found")
    if deletion_request.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Deletion request has already been resolved",
        )

    task = (
        db.get(TaskModel, deletion_request.task_id)
        if deletion_request.task_id is not None
        else None
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The task no longer exists",
        )

    if decision.decision == "approve_delete":
        deletion_request.decided_by_id = reviewer.id
        deletion_request.decision_note = decision.note
        deletion_request.resolved_at = datetime.now(UTC)
        deletion_request.status = "approved"
        related_requests = db.scalars(
            select(TaskDeletionRequest).where(TaskDeletionRequest.task_id == task.id)
        ).all()
        for related_request in related_requests:
            related_request.task_id = None
        db.flush()
        db.delete(task)
    elif decision.decision == "reject":
        deletion_request.decided_by_id = reviewer.id
        deletion_request.decision_note = decision.note
        deletion_request.resolved_at = datetime.now(UTC)
        deletion_request.status = "rejected"
    else:
        assignee = db.scalar(
            select(User).where(User.id == decision.assignee_id).with_for_update()
        )
        if (
            assignee is None
            or not assignee.is_active
            or assignee.role.name != "member"
            or assignee.id == requester.id
            or (reviewer.role.name == "manager" and assignee.manager_id != reviewer.id)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="assignee_id must identify another eligible active member",
            )
        deletion_request.decided_by_id = reviewer.id
        deletion_request.decision_note = decision.note
        deletion_request.resolved_at = datetime.now(UTC)
        task.user_id = assignee.id
        deletion_request.status = "reassigned"
        deletion_request.reassigned_to_id = assignee.id

    db.commit()
    db.refresh(deletion_request)
    return deletion_request
