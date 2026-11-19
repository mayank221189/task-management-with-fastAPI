from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class UserBaseSchema(BaseModel):
    first_name: str
    last_name: str
    username: str
    password: str
    email: str


class RoleResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UserResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    username: str
    email: str
    is_active: bool
    created_at: datetime
    role: RoleResponseSchema
    manager_id: int | None


class LoginRequestSchema(BaseModel):
    username: str
    password: str


class UserAccessUpdateSchema(BaseModel):
    role: Literal["admin", "manager", "member"] | None = None
    manager_id: int | None = None

    @model_validator(mode="after")
    def require_access_change(self) -> "UserAccessUpdateSchema":
        if not {"role", "manager_id"}.intersection(self.model_fields_set):
            raise ValueError("Provide a role or manager_id to update")
        return self
