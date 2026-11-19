from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskSchemaDTO(BaseModel):
    title: str
    description: str
    is_completed: bool = False


class TaskResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    is_completed: bool | None
    user_id: int | None = 0
    created_by_id: int | None = None


class DeletionRequestCreateSchema(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class DeletionReviewSchema(BaseModel):
    decision: Literal["approve_delete", "reject", "reassign"]
    assignee_id: int | None = None
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_decision_fields(self) -> "DeletionReviewSchema":
        if self.decision == "reassign" and self.assignee_id is None:
            raise ValueError("assignee_id is required when reassigning a task")
        if self.decision != "reassign" and self.assignee_id is not None:
            raise ValueError("assignee_id is only valid when reassigning a task")
        return self


class DeletionRequestResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int | None
    original_task_id: int
    task_title: str
    task_description: str | None
    requested_by_id: int | None
    requested_by_username: str
    reason: str | None
    status: Literal["pending", "approved", "rejected", "reassigned"]
    decided_by_id: int | None
    decision_note: str | None
    reassigned_to_id: int | None
    created_at: datetime
    resolved_at: datetime | None
